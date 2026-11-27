#!/usr/bin/env python3
"""Disposable flatd fixture for the iPhone gate. All listeners bind to IPv4 loopback."""

import argparse
import base64
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import RawIOBase
import json
import math
from pathlib import Path
from queue import Empty, SimpleQueue
import re
import secrets
import select
import shutil
import signal
import socket
from socketserver import BaseRequestHandler, ThreadingTCPServer
import ssl
import struct
import subprocess
import threading
import time
from urllib.parse import parse_qs, unquote, urlsplit

LOOPBACK = "127.0.0.1"
DEFAULT_URL = "https://127.0.0.1:8799"
KEYS = ("a", "b", "h")
FAN = "fan:probe"
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
P256_SPKI_PREFIX = bytes.fromhex("3059301306072a8648ce3d020106082a8648ce3d030107034200")
HTTP_IDLE_TIMEOUT = 60
HTTP_REQUEST_TIMEOUT = 10
LOG_METHODS = {"GET", "HEAD", "POST", "PATCH", "OPTIONS"}
LOG_PATHS = {"/api/health", "/api/scenes", "/api/events", "/api/modes", "/api/modes/cooking",
             "/api/devices", f"/api/devices/{FAN}", "/api/remote", "/test/echo"}
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PATCH, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Flatd-Source",
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def openssl(*args, input=None):
    return subprocess.run(["openssl", *args], input=input, capture_output=True, check=True).stdout


def pin(cert):
    public_key = openssl("x509", "-in", str(cert), "-pubkey", "-noout")
    spki = openssl("pkey", "-pubin", "-outform", "der", input=public_key)
    if len(spki) != len(P256_SPKI_PREFIX) + 65 or not spki.startswith(P256_SPKI_PREFIX + b"\x04"):
        raise ValueError("expected a P-256 certificate")
    return hashlib.sha256(spki).hexdigest()


def make_identities(directory, url):
    # Claim a fresh directory before writing anything, including on concurrent invocations.
    directory.mkdir(mode=0o700)
    try:
        for key in KEYS:
            cert = directory / f"{key}.crt"
            private_key = directory / f"{key}.key"
            openssl("ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(private_key))
            private_key.chmod(0o600)
            openssl("req", "-new", "-x509", "-key", str(private_key), "-subj", f"/CN=flatd-probe-{key}",
                    "-days", "7300", "-out", str(cert))
        (directory / "token").write_text(secrets.token_urlsafe(32) + "\n", encoding="ascii")
        (directory / "token").chmod(0o600)
        (directory / "url").write_text(url + "\n", encoding="ascii")
        codes = [(key, pairing_code(directory, key)) for key in KEYS]
    except BaseException:
        shutil.rmtree(directory)
        raise
    for key, code in codes:
        print(f"{key} spki_sha256={code['spki_sha256']}")
        print(json.dumps(code))


def pairing_code(directory, key, url=None):
    return {"url": url or (directory / "url").read_text(encoding="ascii").strip(),
            "token": (directory / "token").read_text(encoding="ascii").strip(),
            "spki_sha256": pin(directory / f"{key}.crt")}


def remote_details(directory, home_pin):
    # B impersonates the advertised listener during the wrong-key run. Home still advertises A.
    absent = {"url": None, "spki_sha256": None}
    try:
        url = (directory / "url").read_text(encoding="ascii").strip()
        if service_url(url) != url:
            return absent
    except (OSError, ValueError, argparse.ArgumentTypeError):
        return absent
    parsed = urlsplit(url)
    labels = parsed.hostname.split(".")
    dns_label = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    if (len(labels) < 2 or all(label.isdecimal() for label in labels)
            or not all(re.fullmatch(dns_label, label) for label in labels) or parsed.port is None):
        return absent
    try:
        remote_pin = pin(directory / "a.crt")
    except (OSError, ValueError, subprocess.CalledProcessError):
        return absent
    return absent if remote_pin == home_pin else {"url": url, "spki_sha256": remote_pin}


class Probe:
    def __init__(self, token, delays):
        self.token, self.delays = token, delays
        self.lock = threading.Lock()
        self.subscribers = set()
        self.fan = {"id": FAN, "kind": "fan", "label": "Probe fan", "default_label": "Probe fan",
                    "room": "test", "driver": "shelly", "controls": ["on"],
                    "state": {"on": False, "online": True, "off_at": None, "updated_at": now()}}
        self.mode = {"id": "cooking", "label": "Cooking", "active": False, "since": None, "devices": [FAN]}

    def subscribe(self, events):
        with self.lock:
            events.put(json.dumps({"type": "snapshot", "devices": [self.fan], "modes": [self.mode]}).encode())
            self.subscribers.add(events)

    def unsubscribe(self, events):
        with self.lock:
            self.subscribers.discard(events)

    def publish(self, event):
        message = json.dumps({**event, "source": "api"}).encode()
        for subscriber in self.subscribers:
            subscriber.put(message)

    def set_fan(self, on):
        if self.fan["state"]["on"] != on:
            state = {"on": on, "online": True, "off_at": None, "updated_at": now()}
            self.fan["state"] = state
            self.publish({"type": "state", "id": FAN, "state": state})
        return self.fan.copy()

    def set_mode(self, active):
        changed = self.mode["active"] != active
        if changed:
            self.mode.update(active=active, since=now() if active else None)
        if changed or active:
            self.set_fan(active)
        if changed:
            self.publish({"type": "mode", "mode": self.mode})
        return {**self.mode, "failed": {}}


def read_exact(read, count):
    data = bytearray()
    while len(data) < count:
        chunk = read(count - len(data))
        if not chunk:
            raise EOFError
        data.extend(chunk)
    return bytes(data)


def read_frame(sock):
    read = sock.recv
    flags, size = read_exact(read, 2)
    if not size & 0x80 or flags & 0x70:
        raise ValueError("invalid WebSocket frame")
    length = size & 0x7f
    if length == 126:
        length, = struct.unpack("!H", read_exact(read, 2))
    elif length == 127:
        length, = struct.unpack("!Q", read_exact(read, 8))
    if length > 1024 * 1024 or (flags & 0x08 and (length > 125 or not flags & 0x80)):
        raise ValueError("invalid WebSocket frame length")
    mask = read_exact(read, 4)
    payload = read_exact(read, length)
    return flags, bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))


def send_frame(sock, flags, payload):
    length = len(payload)
    if length < 126:
        header = bytes([flags, length])
    elif length <= 65535:
        header = struct.pack("!BBH", flags, 126, length)
    else:
        header = struct.pack("!BBQ", flags, 127, length)
    sock.sendall(header + payload)


class RequestReader(RawIOBase):
    """Unbuffered HTTP input with one deadline for the request line, headers and body."""

    def __init__(self, sock):
        self.sock = sock
        self.deadline = None

    def readable(self):
        return True

    def readinto(self, buffer):
        timeout = HTTP_IDLE_TIMEOUT if self.deadline is None else self.deadline - time.monotonic()
        if timeout <= 0:
            raise TimeoutError("HTTP read deadline expired")
        previous_timeout = self.sock.gettimeout()
        self.sock.settimeout(timeout)
        try:
            count = self.sock.recv_into(buffer)
        finally:
            self.sock.settimeout(previous_timeout)
        if count and self.deadline is None:
            self.deadline = time.monotonic() + HTTP_REQUEST_TIMEOUT
        return count


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        # Keep WebSocket bytes in TLS, where pending()/select() can see them after the upgrade.
        self.rfile.close()
        self.rfile = RequestReader(self.connection)

    def log_message(self, *args):
        # The default access log includes the raw target (which may have a token in its query).
        pass

    def handle_one_request(self):
        self.request_logged = False
        self.raw_requestline = b""
        self.rfile.deadline = None
        try:
            super().handle_one_request()
        finally:
            if self.rfile.deadline is not None and not self.request_logged:
                self.record_rejected_request()

    def record_request(self, method, path, bearer, **fields):
        self.server.record(self.client_address, "request",
                           method=method if method in LOG_METHODS else "<other>",
                           path=path if path in LOG_PATHS else "<other>", bearer=bearer, **fields)
        self.request_logged = True

    def record_rejected_request(self):
        words = self.raw_requestline.decode("iso-8859-1").split(None, 2)
        method, target = (words + ["", ""])[:2]
        path = unquote(target.partition("?")[0])
        self.record_request(method, path, "unparsed", parse="rejected")

    def send_error(self, code, message=None, explain=None):
        if not self.request_logged:
            self.record_rejected_request()
        # Use the standard reason. Parser details may quote the request line.
        super().send_error(code)

    def send_response(self, code, message=None):
        super().send_response(code, message)
        for name, value in CORS_HEADERS.items():
            self.send_header(name, value)

    def parse_request(self):
        if not super().parse_request():
            return False
        path, _, query = self.path.partition("?")
        self.route = unquote(path)
        if self.command == "OPTIONS":
            self.record_request(self.command, self.route, "unchecked")
            return True
        header = self.headers.get("Authorization")
        bearer = header == "Bearer " + self.server.probe.token
        verdict = "right" if bearer else ("wrong" if header is not None else "missing")
        self.record_request(self.command, self.route, verdict)
        authorized = bearer or (header is None and self.route == "/api/events"
                                and parse_qs(query).get("token") == [self.server.probe.token])
        if not authorized and (self.command, self.route) != ("GET", "/api/health"):
            self.answer(401, {"error": "unauthorized"}, WWW_Authenticate="Bearer")
            return False
        return True

    def handle_expect_100(self):
        # The parser calls this before we authenticate. Send Continue only when reading a POST body.
        return True

    def answer(self, status, body, **headers):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        if status >= 400:
            self.send_header("Connection", "close")
        for name, value in headers.items():
            self.send_header(name.replace("_", "-"), value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def has_request_body(self):
        return (self.headers.get("Transfer-Encoding") is not None
                or (self.headers.get("Content-Length") is not None
                    and self.headers.get_all("Content-Length") != ["0"]))

    def do_OPTIONS(self):
        self.send_response(204)
        if self.has_request_body():
            self.send_header("Connection", "close")
        self.end_headers()

    def do_GET(self):
        if self.has_request_body():
            return self.answer(400, {"error": "GET does not take a body"})
        time.sleep(self.server.probe.delays.get(self.route, 0))
        if self.route == "/api/remote" and self.server.identity == "h":
            return self.answer(200, remote_details(self.server.directory, self.server.home_pin))
        probe = self.server.probe
        if self.route in ("/api/events", "/test/echo"):
            return self.websocket(echo=self.route == "/test/echo")
        with probe.lock:
            responses = {"/api/health": {"ok": True, "version": "probe"}, "/api/scenes": {"scenes": []},
                         "/api/devices": {"devices": [probe.fan.copy()]}, "/api/modes": {"modes": [probe.mode.copy()]}}
        if self.route in responses:
            self.answer(200, responses[self.route])
        else:
            self.answer(404, {"error": "not found"})

    def do_POST(self):
        probe = self.server.probe
        commands = {"/api/modes/cooking": ("active", probe.set_mode), f"/api/devices/{FAN}": ("on", probe.set_fan)}
        if self.route not in commands:
            return self.answer(404, {"error": "not found"})
        field, command = commands[self.route]
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if (not 0 < length <= 65536 or self.headers.get("Transfer-Encoding") is not None
                    or len(self.headers.get_all("Content-Length", [])) != 1):
                raise ValueError
            if self.request_version >= "HTTP/1.1" and self.headers.get("Expect", "").lower() == "100-continue":
                super().handle_expect_100()
            body = json.loads(read_exact(self.rfile.read, length))
            if not isinstance(body, dict) or not isinstance(body.get(field), bool):
                raise ValueError
        except (ValueError, EOFError):
            return self.answer(400, {"error": f"expected a JSON object with a boolean {field}"})
        time.sleep(probe.delays.get(self.route, 0))
        with probe.lock:
            result = command(body[field])
        self.answer(200, result)

    def websocket(self, echo):
        key = self.headers.get("Sec-WebSocket-Key", "")
        try:
            valid_key = len(base64.b64decode(key, validate=True)) == 16
        except ValueError:
            valid_key = False
        if self.headers.get("Upgrade", "").lower() != "websocket" or not valid_key:
            return self.answer(400, {"error": "WebSocket upgrade required"})
        accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode("ascii")).digest()).decode("ascii")
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        self.close_connection = True
        self.rfile.deadline = None
        sock = self.connection
        sock.settimeout(None)

        probe = self.server.probe
        events = SimpleQueue()
        if not echo:
            probe.subscribe(events)
        try:
            while True:
                try:
                    while not echo:
                        send_frame(sock, 0x81, events.get_nowait())
                except Empty:
                    pass
                # One worker owns all TLS reads and writes. Echo has no queue to poll.
                if not sock.pending() and not select.select([sock], [], [], None if echo else 0.05)[0]:
                    continue
                flags, payload = read_frame(sock)
                opcode = flags & 0x0f
                if opcode == 8:
                    send_frame(sock, 0x88, payload)
                    return
                if opcode == 9:
                    send_frame(sock, 0x8a, payload)
                elif echo and opcode in (0, 1, 2):
                    send_frame(sock, flags, payload)
        except (EOFError, OSError, ValueError):
            pass
        finally:
            if not echo:
                probe.unsubscribe(events)


@dataclass
class Connection:
    sock: socket.socket
    handshaking: bool


class ConnectionLog:
    uses_tls = False

    def __init__(self, address, handler, *, label, log):
        self.identity, self.log = label, log
        self.connections = {}
        self.connections_lock = threading.Lock()
        super().__init__(address, handler)

    def record(self, peer, event, **fields):
        with self.connections_lock:
            connection = self.connections.get(peer)
            if connection is not None:
                if event == "tls_handshake":
                    connection.handshaking = False
                self.log_connection(peer, event, **fields)

    def log_connection(self, peer, event, **fields):
        self.log(event, listener=self.identity, port=self.server_port, peer=f"{peer[0]}:{peer[1]}", **fields)

    def get_request(self):
        sock, peer = super().get_request()
        with self.connections_lock:
            self.connections[peer] = Connection(sock, self.uses_tls)
            self.log_connection(peer, "tcp_accept")
        return sock, peer

    def process_request_thread(self, request, peer):
        try:
            super().process_request_thread(request, peer)
        finally:
            with self.connections_lock:
                connection = self.connections.pop(peer, None)
                if connection is not None:
                    self.log_close(peer, connection, "connection closed during handshake")

    def log_close(self, peer, connection, reason):
        if connection.handshaking:
            self.log_connection(peer, "tls_handshake", result="failed", reason=reason)
        self.log_connection(peer, "tcp_close")

    def server_close(self):
        super().server_close()
        # The worker threads are daemons so a timed gate request can't postpone shutdown.
        with self.connections_lock:
            for peer, connection in self.connections.items():
                try:
                    connection.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                connection.sock.close()
                self.log_close(peer, connection, "listener stopped during handshake")
            self.connections.clear()


class TLSServer(ConnectionLog, ThreadingHTTPServer):
    uses_tls = True

    def __init__(self, port, directory, key, probe, log):
        self.directory = directory
        self.home_pin = pin(directory / "h.crt") if key == "h" else None
        self.probe = probe
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.minimum_version = ssl.TLSVersion.TLSv1_2
        # In TLS 1.2 a client refusal of the server certificate can fail the server's handshake
        # before it completes. TLS 1.3 permits some clients to report the refusal later.
        self.context.maximum_version = ssl.TLSVersion.TLSv1_2
        self.context.load_cert_chain(directory / f"{key}.crt", directory / f"{key}.key")
        super().__init__((LOOPBACK, port), Handler, label=key, log=log)

    def finish_request(self, request, peer):
        try:
            with self.connections_lock:
                connection = self.connections.get(peer)
                if connection is None:
                    return
                request.settimeout(5)
                tls = self.context.wrap_socket(request, server_side=True, do_handshake_on_connect=False)
                connection.sock = tls
            with tls:
                try:
                    tls.do_handshake()
                except OSError as error:
                    self.record(peer, "tls_handshake", result="failed", reason=str(error))
                    return
                self.record(peer, "tls_handshake", result="ok")
                super().finish_request(tls, peer)
        except OSError:
            pass  # The phone may close while a delayed response is in flight.


class Relay(ConnectionLog, ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port, target, log):
        self.target = target
        super().__init__((LOOPBACK, port), RelayHandler, label="relay", log=log)

    @property
    def server_port(self):
        return self.server_address[1]


class RelayHandler(BaseRequestHandler):
    @staticmethod
    def copy(source, destination):
        try:
            while chunk := source.recv(65536):
                destination.sendall(chunk)
        except OSError:
            # Unblock the other direction on a reset or failed write.
            for sock in (source, destination):
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        else:
            try:
                destination.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    def handle(self):
        try:
            upstream = socket.create_connection(self.server.target, timeout=5)
        except OSError as error:
            self.server.record(self.client_address, "relay_error", reason=str(error))
            return
        with upstream:
            upstream.settimeout(None)
            forward = threading.Thread(target=self.copy, args=(self.request, upstream), daemon=True)
            forward.start()
            self.copy(upstream, self.request)
            forward.join()


def service_url(value):
    if any(char.isspace() for char in value) or "?" in value or "#" in value:
        raise argparse.ArgumentTypeError("expected an HTTPS base URL")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.path not in ("", "/") or parsed.netloc.endswith(":")):
        raise argparse.ArgumentTypeError("expected an HTTPS base URL")
    if parsed.port == 0:
        raise argparse.ArgumentTypeError("expected a nonzero URL port")
    value.encode("ascii")
    return value.rstrip("/")


def delay(value):
    path, _, seconds_text = value.partition("=")
    seconds = float(seconds_text)
    if not path.startswith("/") or not math.isfinite(seconds) or seconds < 0:
        raise argparse.ArgumentTypeError("expected /path=seconds with a finite, nonnegative delay")
    return path, seconds


def relay_address(values):
    port, target = values
    address = urlsplit("//" + (f"{LOOPBACK}:{target}" if target.isdecimal() else target))
    if not address.hostname or not address.port or address.username is not None or address.path or address.query or address.fragment:
        raise ValueError("relay target must be PORT or HOST:PORT")
    return listen_port(port), (address.hostname, address.port)


def listen_port(value):
    port = int(value)
    if not 0 <= port <= 65535:
        raise ValueError("listen port must be between 0 and 65535")
    return port


def run_servers(args):
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    with ExitStack() as stack:
        logfile = stack.enter_context(args.log.open("x", encoding="utf-8")) if args.log else None
        log_lock = threading.Lock()

        def log(event, **fields):
            line = json.dumps({"time": now(), "event": event, **fields})
            with log_lock:
                print(line, flush=True)
                if logfile:
                    print(line, file=logfile, flush=True)

        servers = []
        if args.action == "serve":
            token = (args.dir / "token").read_text(encoding="ascii").strip()
            probe = Probe(token, dict(args.delay))
            servers.append(stack.enter_context(TLSServer(args.port, args.dir, args.key, probe, log)))
            if args.home_port is not None:
                servers.append(stack.enter_context(TLSServer(args.home_port, args.dir, "h", probe, log)))
        if args.relay:
            port, target = relay_address(args.relay)
            servers.append(stack.enter_context(Relay(port, target, log)))
        for server in servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
            stack.callback(server.shutdown)
            log("ready", listener=server.identity, host=LOOPBACK, port=server.server_port)
        stop.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--relay", nargs=2, metavar=("PORT", "TARGET"))
    parser.add_argument("--log", type=Path, help="write JSON lines to a new file")
    commands = parser.add_subparsers(dest="action")
    make = commands.add_parser("make-identities", help="create A, B, H and the dummy token in a new directory")
    make.add_argument("dir", type=Path)
    make.add_argument("--url", type=service_url, default=DEFAULT_URL)
    pairing = commands.add_parser("pairing-code", help="print one pairing JSON from the stored identities")
    pairing.add_argument("dir", type=Path)
    pairing.add_argument("--key", required=True, choices=KEYS)
    pairing.add_argument("--url", type=service_url)
    serve = commands.add_parser("serve", help="start the TLS probe")
    serve.add_argument("--dir", required=True, type=Path)
    serve.add_argument("--key", required=True, choices=KEYS[:2])
    serve.add_argument("--port", type=listen_port, default=8799)
    serve.add_argument("--home-port", type=listen_port)
    serve.add_argument("--delay", type=delay, action="append", default=[])
    serve.add_argument("--relay", nargs=2, metavar=("PORT", "TARGET"), default=argparse.SUPPRESS)
    serve.add_argument("--log", type=Path, default=argparse.SUPPRESS, help="write JSON lines to a new file")
    args = parser.parse_args()
    try:
        if args.action == "make-identities":
            make_identities(args.dir, args.url)
        elif args.action == "pairing-code":
            print(json.dumps(pairing_code(args.dir, args.key, args.url)))
        elif args.action == "serve" or args.relay:
            run_servers(args)
        else:
            parser.error("choose a subcommand or --relay PORT TARGET")
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"probe: {error}\n")


if __name__ == "__main__":
    main()
