"""P2b probe checks. Connected socket pairs also exercise TLS in sandboxes that deny bind()."""

from contextlib import contextmanager
import base64
from datetime import datetime
import hashlib
from http.client import HTTPSConnection
import importlib
import json
from pathlib import Path
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

probe = importlib.import_module(f"{__package__}.probe_service" if __package__ else "probe_service")
SCRIPT = Path(probe.__file__)
REMOTE_URL = "https://probe.example.net:8443"
PEER = ("127.0.0.1", 54321)


class ProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        cls.directory = Path(temp.name) / "ids"
        cls.created = cls.cli("make-identities", cls.directory, "--url", REMOTE_URL).stdout.splitlines()
        cls.codes = dict(zip(probe.KEYS, map(json.loads, cls.created[1::2])))
        cls.token = cls.codes["a"]["token"]

    @classmethod
    def cli(cls, *args, check=True):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], check=check, capture_output=True,
                              text=True, timeout=10)

    def setUp(self):
        self.records = []
        self.flat = probe.Probe(self.token, {})

    def log(self, event, **fields):
        self.records.append({"event": event, **fields})

    def context(self, key):
        # Each fixture certificate is self-signed and holds the public key in that pairing code.
        # Python's TLS verifier trusts only that fixture anchor and aborts before sending HTTP.
        context = ssl.create_default_context(cafile=str(self.directory / f"{key}.crt"))
        context.check_hostname = False
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT
        return context

    @contextmanager
    def accepted_connection(self, key):
        # Exercise the actual accept, handshake, request and close hooks over a bidirectional socket pair.
        with patch.object(probe.TLSServer, "server_bind"), patch.object(probe.TLSServer, "server_activate"):
            server = probe.TLSServer(0, self.directory, key, self.flat, self.log)
        with server:
            server.server_port = 8799
            client, accepted = socket.socketpair()
            with client, accepted:
                with patch.object(server, "socket") as listener:
                    listener.accept.return_value = (accepted, PEER)
                    request, peer = server.get_request()
                worker = threading.Thread(target=server.process_request_thread, args=(request, peer), daemon=True)
                worker.start()
                client.settimeout(3)
                try:
                    yield client
                finally:
                    client.close()
                    worker.join(4)
                    self.assertFalse(worker.is_alive(), "connection handler did not stop")

    @contextmanager
    def connection(self, *, key="a", trust="a"):
        with self.accepted_connection(key) as client, self.context(trust).wrap_socket(client) as tls:
            yield tls

    def pinned_handshake(self, client, expected_pin):
        # Inspect the TLS 1.2 Certificate message before passing it to the TLS engine. This
        # checks the wire SPKI before the client sends its Finished, with no CA or hostname check.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        incoming, outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
        tls = context.wrap_bio(incoming, outgoing)
        handshake = bytearray()
        pinned = False
        while True:
            try:
                tls.do_handshake()
                client.sendall(outgoing.read())
                self.assertTrue(pinned, "TLS completed without a pin check")
                return
            except ssl.SSLWantReadError:
                client.sendall(outgoing.read())
            header = probe.read_exact(client.recv, 5)
            payload = probe.read_exact(client.recv, int.from_bytes(header[3:], "big"))
            if not pinned:
                self.assertEqual(header[0], 22)  # TLS handshake record
                handshake.extend(payload)
                while len(handshake) >= 4:
                    end = 4 + int.from_bytes(handshake[1:4], "big")
                    if len(handshake) < end:
                        break
                    if handshake[0] == 11:  # Certificate, with a 3-byte list and leaf length
                        leaf_length = int.from_bytes(handshake[7:10], "big")
                        leaf = bytes(handshake[10:10 + leaf_length])
                        public = probe.openssl("x509", "-inform", "der", "-pubkey", "-noout", input=leaf)
                        spki = probe.openssl("pkey", "-pubin", "-outform", "der", input=public)
                        if hashlib.sha256(spki).hexdigest() != expected_pin:
                            raise ssl.SSLCertVerificationError("SPKI pin mismatch")
                        pinned = True
                        break
                    del handshake[:end]
            incoming.write(header + payload)

    @contextmanager
    def http(self, key="a"):
        with self.connection(key=key, trust=key) as tls:
            connection = HTTPSConnection("localhost")
            connection.sock = tls
            try:
                yield connection
            finally:
                connection.close()

    @staticmethod
    def send_request(connection, method, path, *, token=None, body=None):
        headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
        connection.request(method, path, json.dumps(body) if body is not None else None, headers)
        with connection.getresponse() as response:
            data = response.read()
            return response.status, json.loads(data) if data else None, response.headers

    def request(self, method, path, *, token=None, body=None, key="a"):
        with self.http(key) as connection:
            return self.send_request(connection, method, path, token=token, body=body)

    @staticmethod
    def upgrade(tls, path, token=None):
        key = base64.b64encode(bytes(range(16))).decode()
        auth = f"Authorization: Bearer {token}\r\n" if token else ""
        tls.sendall((f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: Upgrade\r\n"
                     f"Upgrade: websocket\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
                     f"{auth}\r\n").encode())
        with tls.makefile("rb", buffering=0) as reader:
            status = reader.readline().decode().strip()
            headers = {}
            while line := reader.readline().strip():
                name, value = line.decode().split(":", 1)
                headers[name.lower()] = value.strip()
        return status, headers

    @staticmethod
    def frame(tls):
        opcode, length = probe.read_exact(tls.recv, 2)
        if length == 126:
            length, = struct.unpack("!H", probe.read_exact(tls.recv, 2))
        return opcode, probe.read_exact(tls.recv, length)

    @staticmethod
    def masked_frame(opcode, payload):
        mask = b"test"
        masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        return bytes([opcode, len(payload) | 0x80]) + mask + masked

    def send_frame(self, tls, opcode, payload):
        tls.sendall(self.masked_frame(opcode, payload))

    def test_identities_are_distinct_and_never_overwritten(self):
        originals = {path.name: path.read_bytes() for path in self.directory.iterdir()}
        self.assertNotEqual(self.cli("make-identities", self.directory, check=False).returncode, 0)
        self.assertEqual({path.name: path.read_bytes() for path in self.directory.iterdir()}, originals)
        pins = set()
        for key, line in zip(probe.KEYS, self.created[::2]):
            with self.subTest(key=key):
                saved = self.codes[key]
                self.assertEqual(saved["url"], REMOTE_URL)
                self.assertEqual(saved["token"], self.token)
                self.assertRegex(saved["spki_sha256"], r"^[0-9a-f]{64}$")
                self.assertEqual(line, f"{key} spki_sha256={saved['spki_sha256']}")
                # Arestia's FlatdPin.swift reconstructs this P-256 SubjectPublicKeyInfo from the raw point.
                public = probe.openssl("x509", "-in", str(self.directory / f"{key}.crt"), "-pubkey", "-noout")
                spki = probe.openssl("pkey", "-pubin", "-outform", "der", input=public)
                self.assertEqual(spki[:26].hex(), "3059301306072a8648ce3d020106082a8648ce3d030107034200")
                self.assertEqual(len(spki), 26 + 65)
                self.assertEqual(spki[26], 4)
                self.assertEqual(hashlib.sha256(spki).hexdigest(), saved["spki_sha256"])
                reloaded = json.loads(self.cli("pairing-code", self.directory, "--key", key).stdout)
                self.assertEqual(reloaded, saved)
                pins.add(reloaded["spki_sha256"])
        self.assertEqual(len(pins), 3)
        self.assertRegex(self.token, r"^[A-Za-z0-9_-]{43}$")
        home = json.loads(self.cli("pairing-code", self.directory, "--key", "h",
                                   "--url", "https://127.0.0.1:8801").stdout)
        self.assertEqual(home, {**self.codes["h"], "url": "https://127.0.0.1:8801"})

    def test_wrong_bearer_is_refused_and_neither_token_is_logged(self):
        wrong = "example-wrong-bearer"
        status, body, headers = self.request("GET", f"/api/scenes?token={self.token}", token=wrong)
        self.assertEqual((status, headers["WWW-Authenticate"]), (401, "Bearer"))
        self.assertIn("error", body)
        self.assertEqual([r["event"] for r in self.records], ["tcp_accept", "tls_handshake", "request", "tcp_close"])
        self.assertEqual(self.records[1]["result"], "ok")
        request = self.records[2]
        self.assertEqual((request["method"], request["path"], request["bearer"]), ("GET", "/api/scenes", "wrong"))
        self.assertNotIn(self.token, json.dumps(self.records))
        self.assertNotIn(wrong, json.dumps(self.records))
        self.assertEqual(self.request("GET", f"/api/health?token={self.token}")[1], {"ok": True, "version": "probe"})
        self.assertEqual(self.records[-2]["bearer"], "missing")
        self.assertEqual(self.request("GET", "/api/scenes", token=self.token)[1], {"scenes": []})
        self.assertEqual(self.records[-2]["bearer"], "right")

    def test_wrong_bearer_refused_before_method_dispatch(self):
        for method in ("PATCH", "HEAD"):
            with self.subTest(method=method):
                status, _, headers = self.request(method, "/api/devices/fan:probe", token="wrong")
                self.assertEqual((status, headers["WWW-Authenticate"]), (401, "Bearer"))
                self.assertEqual((self.records[-2]["method"], self.records[-2]["bearer"]), (method, "wrong"))
        self.assertEqual(self.request("GET", "/api/health", token="wrong")[0], 200)

    def test_options_returns_flatd_cors_headers_before_auth(self):
        with self.http() as connection:
            for token in (None, "wrong"):
                with self.subTest(token=token):
                    status, body, headers = self.send_request(connection, "OPTIONS", "/api/devices", token=token)
                    self.assertEqual((status, body), (204, None))
                    self.assertEqual(headers["Access-Control-Allow-Origin"], "*")
                    self.assertEqual(headers["Access-Control-Allow-Methods"], "GET, POST, PATCH, OPTIONS")
                    self.assertEqual(headers["Access-Control-Allow-Headers"], "Authorization, Content-Type, X-Flatd-Source")
                    self.assertNotIn("Content-Length", headers)
                    self.assertNotIn("WWW-Authenticate", headers)
            self.assertEqual(self.send_request(connection, "GET", "/api/devices")[0], 401)
        preflights = [r["bearer"] for r in self.records if r.get("method") == "OPTIONS"]
        self.assertEqual(preflights, ["unchecked", "unchecked"])

    def test_two_http_requests_reuse_the_tls_connection(self):
        with self.http() as connection:
            tls = connection.sock
            status, _, headers = self.send_request(connection, "GET", "/api/health")
            self.assertEqual(status, 200)
            self.assertNotIn("Connection", headers)
            status, _, headers = self.send_request(connection, "POST", "/api/devices/fan:probe",
                                                   token=self.token, body={"on": True})
            self.assertEqual(status, 200)
            self.assertNotIn("Connection", headers)
            self.assertIs(connection.sock, tls)
        self.assertEqual([r["event"] for r in self.records],
                         ["tcp_accept", "tls_handshake", "request", "request", "tcp_close"])

    def test_rejected_parse_logs_sanitized_method_and_path(self):
        with self.http() as connection:
            self.assertEqual(self.send_request(connection, "GET", "/api/health")[0], 200)
            tls = connection.sock
            tls.sendall(f"GET /api/%73cenes?token={self.token} HTTP/2.0\r\n".encode())
            tls.recv(1)
        self.assertEqual([r["event"] for r in self.records],
                         ["tcp_accept", "tls_handshake", "request", "request", "tcp_close"])
        request = self.records[-2]
        self.assertEqual((request["method"], request["path"], request["bearer"], request["parse"]),
                         ("GET", "/api/scenes", "unparsed", "rejected"))
        logs = json.dumps(self.records)
        for private in (self.token, "HTTP/2.0"):
            self.assertNotIn(private, logs)

    def test_device_post_routes_and_logs_one_decode(self):
        # FlatdClient.pathID("fan:probe") keeps the colon and produces the first spelling.
        for device_id, expected_status, expected_path in (
            ("fan:probe", 200, "/api/devices/fan:probe"),
            ("fan%3Aprobe", 200, "/api/devices/fan:probe"),
            ("fan%253Aprobe", 404, "<other>"),
        ):
            with self.subTest(device_id=device_id):
                status, _, _ = self.request("POST", f"/api/devices/{device_id}", token=self.token, body={"on": True})
                self.assertEqual(status, expected_status)
                self.assertEqual(self.records[-2]["path"], expected_path)

    def test_request_logs_hide_a_credential_in_the_method_path_and_header(self):
        credential = "example-private-bearer"
        path = f"/api/devices/{credential}"
        self.assertEqual(self.request(credential, path, token=credential)[0], 401)
        with self.connection() as tls:
            tls.sendall((f"{credential} {path} HTTP/2.0\r\n"
                         f"Authorization: Bearer {credential}\r\n\r\n").encode())
            try:
                tls.recv(1)
            except (BrokenPipeError, ConnectionResetError):
                pass  # The parser can close the connection with unread headers still in flight.
        requests = [r for r in self.records if r["event"] == "request"]
        self.assertEqual([(r["method"], r["path"], r["bearer"]) for r in requests],
                         [("<other>", "<other>", "wrong"), ("<other>", "<other>", "unparsed")])
        self.assertEqual(requests[-1]["parse"], "rejected")
        self.assertNotIn(credential, json.dumps(self.records))

    @patch.object(probe, "HTTP_REQUEST_TIMEOUT", 0.2)
    def test_stalled_header_closes_a_reused_connection(self):
        with self.http() as connection:
            self.assertEqual(self.send_request(connection, "GET", "/api/health")[0], 200)
            tls = connection.sock
            tls.sendall(b"GET /api/scenes HTTP/1.1\r\nHost: local")
            try:
                self.assertEqual(tls.recv(1), b"")
            except (BrokenPipeError, ConnectionResetError):
                pass  # TLS can report an abrupt peer close as a socket error.
        request, closed = self.records[-2:]
        self.assertEqual((request["path"], request["parse"], closed["event"]),
                         ("/api/scenes", "rejected", "tcp_close"))

    def test_client_pinning_a_rejects_b_before_http_and_reconnects_to_a(self):
        pin = self.codes["a"]["spki_sha256"]
        with self.assertRaisesRegex(ssl.SSLCertVerificationError, "SPKI pin mismatch"):
            with self.accepted_connection("b") as client:
                self.pinned_handshake(client, pin)
        self.assertEqual([r["event"] for r in self.records], ["tcp_accept", "tls_handshake", "tcp_close"])
        self.assertEqual(self.records[1]["result"], "failed")
        self.assertTrue(self.records[1]["reason"])
        with self.accepted_connection("a") as client:
            self.pinned_handshake(client, pin)
        self.assertEqual(self.records[-2]["result"], "ok")
        self.assertEqual(self.request("GET", "/api/health")[0], 200)

    def test_stopping_listener_logs_unfinished_handshake_and_close(self):
        with patch.object(probe.TLSServer, "server_bind"), patch.object(probe.TLSServer, "server_activate"):
            server = probe.TLSServer(0, self.directory, "a", self.flat, self.log)
        with server:
            server.server_port = 8799
            client, accepted = socket.socketpair()
            with client, accepted:
                client.settimeout(2)
                with patch.object(server, "socket") as listener:
                    listener.accept.return_value = (accepted, PEER)
                    request, peer = server.get_request()
                worker = threading.Thread(target=server.process_request_thread, args=(request, peer), daemon=True)
                worker.start()
                server.server_close()
                self.assertEqual(client.recv(1), b"")
                client.close()
                # A TLS read already waiting on the closed descriptor can take its full timeout.
                worker.join(6)
                self.assertFalse(worker.is_alive())
        self.assertEqual([r["event"] for r in self.records], ["tcp_accept", "tls_handshake", "tcp_close"])
        self.assertEqual(self.records[1]["result"], "failed")
        self.assertEqual(self.records[1]["reason"], "listener stopped during handshake")

    def test_home_reloads_valid_remote_details_with_token(self):
        self.assertEqual(self.request("GET", "/api/remote", key="h")[0], 401)
        url_file, cert = self.directory / "url", self.directory / "a.crt"
        self.addCleanup(url_file.write_bytes, url_file.read_bytes())
        self.addCleanup(cert.write_bytes, cert.read_bytes())
        absent = {"url": None, "spki_sha256": None}
        with self.http("h") as connection:
            for url in (REMOTE_URL, "https://new-probe.example.net:9443", "http://probe.example.net:8443",
                        "https://probe.example.net:8443/path", "https://127.0.0.1:8443", None):
                with self.subTest(url=url):
                    if url is None:
                        url_file.unlink()
                    else:
                        url_file.write_text(url + "\n", encoding="ascii")
                    expected = ({"url": url, "spki_sha256": self.codes["a"]["spki_sha256"]}
                                if url in (REMOTE_URL, "https://new-probe.example.net:9443") else absent)
                    status, body, _ = self.send_request(connection, "GET", "/api/remote", token=self.token)
                    self.assertEqual((status, body), (200, expected))
            url_file.write_text(REMOTE_URL + "\n", encoding="ascii")
            for invalid_cert in (b"invalid certificate", (self.directory / "h.crt").read_bytes()):
                cert.write_bytes(invalid_cert)
                self.assertEqual(self.send_request(connection, "GET", "/api/remote", token=self.token)[1], absent)

    @patch.object(probe, "HTTP_REQUEST_TIMEOUT", 0.15)
    def test_endpoint_delay_holds_the_answer(self):
        self.flat.delays["/api/modes/cooking"] = 0.2
        started = time.monotonic()
        status, mode, _ = self.request("POST", "/api/modes/cooking", token=self.token, body={"active": True})
        self.assertGreaterEqual(time.monotonic() - started, 0.2)
        self.assertEqual(status, 200)
        self.assertEqual((mode["active"], mode["failed"]), (True, {}))
        self.assertTrue(self.request("GET", "/api/modes", token=self.token)[1]["modes"][0]["active"])

    def test_snapshot_and_updates_match_arestia_flat_event_and_models(self):
        with self.connection() as stream:
            status, headers = self.upgrade(stream, "/api/events", self.token)
            self.assertEqual(status, "HTTP/1.1 101 Switching Protocols")
            self.assertEqual(headers["upgrade"], "websocket")
            opcode, data = self.frame(stream)
            self.assertEqual(opcode, 0x81)
            snapshot = json.loads(data)
            # FlatEvent.Envelope takes devices/modes arrays. Device and FlatMode use these coding keys.
            self.assertEqual(snapshot["type"], "snapshot")
            fan, = snapshot["devices"]
            self.assertEqual((fan["id"], fan["kind"], fan["label"], fan["default_label"]),
                             ("fan:probe", "fan", "Probe fan", "Probe fan"))
            self.assertEqual(fan["controls"], ["on"])
            self.assertIs(fan["state"]["on"], False)
            self.assertIs(fan["state"]["online"], True)
            self.assertIsNone(fan["state"]["off_at"])
            datetime.fromisoformat(fan["state"]["updated_at"].replace("Z", "+00:00"))
            mode, = snapshot["modes"]
            self.assertEqual(mode, {"id": "cooking", "label": "Cooking", "active": False, "since": None,
                                    "devices": ["fan:probe"]})
            self.assertEqual(self.request("GET", "/api/devices", token=self.token)[1], {"devices": [fan]})

            status, updated, _ = self.request("POST", "/api/devices/fan%3Aprobe", token=self.token, body={"on": True})
            self.assertEqual(status, 200)
            self.assertIs(updated["state"]["on"], True)
            event = json.loads(self.frame(stream)[1])
            self.assertEqual(event, {"type": "state", "id": "fan:probe", "state": updated["state"], "source": "api"})

            status, mode, _ = self.request("POST", "/api/modes/cooking", token=self.token, body={"active": True})
            self.assertEqual(status, 200)
            self.assertEqual(mode.pop("failed"), {})
            self.assertEqual(json.loads(self.frame(stream)[1]), {"type": "mode", "mode": mode, "source": "api"})
            datetime.fromisoformat(mode["since"].replace("Z", "+00:00"))
            self.send_frame(stream, 0x89, b"ping")
            self.assertEqual(self.frame(stream), (0x8a, b"ping"))
            self.send_frame(stream, 0x88, b"")
            self.assertEqual(self.frame(stream), (0x88, b""))
        self.assertNotIn(self.token, json.dumps(self.records))

    def test_echo_keeps_text_and_binary_message_types(self):
        with self.connection() as stream:
            status, headers = self.upgrade(stream, "/test/echo", self.token)
            self.assertEqual(status, "HTTP/1.1 101 Switching Protocols")
            self.assertEqual(headers["sec-websocket-accept"], "Bz3qJYTGdOe8gUSpLosEdiLKDrk=")
            for opcode, payload in ((0x81, b"x" * 100), (0x82, bytes(range(100)))):
                self.send_frame(stream, opcode, payload)
                self.assertEqual(self.frame(stream), (opcode, payload))

    def test_websockets_stay_open_and_read_split_frames_past_http_deadline(self):
        with self.connection() as events, self.connection() as echo:
            for stream, path in ((events, "/api/events"), (echo, "/test/echo")):
                status, _ = self.upgrade(stream, path, self.token)
                self.assertEqual(status, "HTTP/1.1 101 Switching Protocols")
            self.assertEqual(json.loads(self.frame(events)[1])["type"], "snapshot")

            time.sleep(15.1)
            payload = bytes(range(100))
            ping = self.masked_frame(0x89, b"alive")
            message = self.masked_frame(0x82, payload)
            events.sendall(ping[:7])
            echo.sendall(message[:7])
            # The gap exceeds the full HTTP read budget as well as the TLS handshake timeout.
            time.sleep(probe.HTTP_REQUEST_TIMEOUT + 0.25)
            events.sendall(ping[7:])
            echo.sendall(message[7:])
            self.assertEqual(self.frame(events), (0x8a, b"alive"))
            self.assertEqual(self.frame(echo), (0x82, payload))

    def test_relay_copies_both_directions_and_propagates_half_close(self):
        client, incoming = socket.socketpair()
        outgoing, upstream = socket.socketpair()
        with client, incoming, outgoing, upstream:
            client.settimeout(2)
            upstream.settimeout(2)
            with patch.object(probe.Relay, "server_bind"), patch.object(probe.Relay, "server_activate"):
                server = probe.Relay(0, ("127.0.0.1", 8799), self.log)
            with server, patch.object(probe.socket, "create_connection", return_value=outgoing) as connect:
                worker = threading.Thread(target=server.process_request_thread, args=(incoming, PEER), daemon=True)
                worker.start()
                try:
                    data = bytes(range(256)) * 300
                    for start in range(0, len(data), 4096):
                        chunk = data[start:start + 4096]
                        client.sendall(chunk)
                        self.assertEqual(probe.read_exact(upstream.recv, len(chunk)), chunk)
                    client.shutdown(socket.SHUT_WR)
                    self.assertEqual(upstream.recv(1), b"")
                    upstream.sendall(b"reply after EOF")
                    upstream.shutdown(socket.SHUT_WR)
                    self.assertEqual(probe.read_exact(client.recv, 15), b"reply after EOF")
                    self.assertEqual(client.recv(1), b"")
                    worker.join(2)
                    self.assertFalse(worker.is_alive())
                    connect.assert_called_once_with(("127.0.0.1", 8799), timeout=5)
                finally:
                    client.close()
                    upstream.close()
                    worker.join(2)

    def test_loopback_cli_and_log_file(self):
        with socket.socket() as check:
            try:
                check.bind(("127.0.0.1", 0))
            except PermissionError as error:
                self.skipTest(f"loopback bind denied: {error}")
        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "probe.log"
            command = [sys.executable, str(SCRIPT), "serve", "--dir", str(self.directory), "--key", "b",
                       "--port", "0", "--home-port", "0", "--log", str(logfile)]
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
                try:
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline and process.poll() is None:
                        if logfile.exists():
                            entries = [json.loads(line) for line in logfile.read_text().splitlines()]
                            ports = {r["listener"]: r["port"] for r in entries if r["event"] == "ready"}
                            if len(ports) == 2:
                                break
                        time.sleep(0.02)
                    else:
                        self.fail("probe failed to start both TLS listeners")
                    for key, path in (("b", "/api/health"), ("h", "/api/remote")):
                        client = HTTPSConnection("127.0.0.1", ports[key], context=self.context(key), timeout=3)
                        try:
                            client.request("GET", path, headers={"Authorization": f"Bearer {self.token}"})
                            with client.getresponse() as response:
                                self.assertEqual(response.status, 200)
                                body = json.load(response)
                                if key == "h":
                                    self.assertEqual(body["spki_sha256"], self.codes["a"]["spki_sha256"])
                        finally:
                            client.close()
                finally:
                    process.terminate()
                    try:
                        stdout, stderr = process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate()
                        raise
                self.assertEqual(process.returncode, 0, stderr)
                entries = [json.loads(line) for line in logfile.read_text().splitlines()]
                self.assertEqual(stdout, logfile.read_text())
                self.assertEqual([r["listener"] for r in entries if r["event"] == "request"], ["b", "h"])
                self.assertNotIn(self.token, stdout)

    def test_cli_refuses_to_reuse_existing_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "probe.log"
            logfile.write_text("old run\n", encoding="utf-8")
            result = self.cli("serve", "--dir", self.directory, "--key", "b",
                              "--log", logfile, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("File exists", result.stderr)
            self.assertEqual(logfile.read_text(encoding="utf-8"), "old run\n")


if __name__ == "__main__":
    unittest.main()
