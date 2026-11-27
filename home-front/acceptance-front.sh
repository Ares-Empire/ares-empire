#!/usr/bin/env bash
set -euo pipefail

exec python3 - "$@" <<'PY'
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
import os
from pathlib import Path
import runpy
import shlex
import socket
import socketserver
import ssl
import subprocess
import tempfile
import threading
import time

UNIT = "haproxy.service"
PROGRAM = "/usr/local/sbin/home-front"
ROUTES = Path("/etc/home-front/routes")
LOCK = Path("/var/lib/home-front/front-locked")
MAP = Path("/etc/haproxy/home.map")
CFG = Path("/etc/haproxy/haproxy.cfg")
BOOT = Path("/proc/sys/kernel/random/boot_id")
CHECKPOINT = Path("/var/lib/home-front/acceptance-front")
FIXTURES = {"probe": 20099, "probe2": 20097}
PORT = 8443
UNKNOWN = "aaaaaaaaaaaaaaaa"


def run(*argv, code=0, timeout=40):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    require(result.returncode == code, f"{argv[0]} {argv[1]} exited {result.returncode}\n{result.stdout}{result.stderr}")
    return (result.stdout + (result.stderr if code else "")).strip()


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def wait_for(check, message, timeout=5):
    deadline = time.monotonic() + timeout
    while not check():
        require(time.monotonic() < deadline, message)
        time.sleep(0.05)


def raw_hello(address, name=None, port=PORT):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    hello = ssl.MemoryBIO()
    client = context.wrap_bio(ssl.MemoryBIO(), hello, server_hostname=name)
    try:
        client.do_handshake()
    except ssl.SSLWantReadError:
        pass
    with socket.create_connection((address, port), timeout=7) as conn:
        conn.sendall(hello.read())
        try:
            return conn.recv(1)
        except ConnectionResetError:
            return b""


def refusal(address, name):
    require(raw_hello(address, name) == b"", "a closed name or a ClientHello without SNI returned bytes")


def tls(address, name, port=PORT):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # The Mac fixture uses a disposable self-signed certificate.
    with socket.create_connection((address, port), timeout=7) as connection:
        return context.wrap_socket(connection, server_hostname=name)


def exchange(connection):
    connection.sendall(b"12345\n")
    received = b""
    while len(received) < 6:
        chunk = connection.recv(6 - len(received))
        if not chunk:
            return False
        received += chunk
    require(received == b"54321\n", "wrong fixture echo")
    return True


def echo(connection):
    require(exchange(connection), "stream ended before the echo")


@contextmanager
def streaming(connection):
    ready = threading.Event()
    stop = threading.Event()

    def transfer():
        try:
            while not stop.is_set():
                if not exchange(connection):
                    return True
                ready.set()
                stop.wait(0.05)
        except (BrokenPipeError, ConnectionResetError, ssl.SSLEOFError):
            return True
        return False

    with ThreadPoolExecutor(max_workers=1) as pool:
        stream = pool.submit(transfer)
        try:
            require(ready.wait(7) and not stream.done(), "could not establish the streaming TLS client")
            yield stream
        finally:
            stop.set()


def ended(connection):
    try:
        require(connection.recv(1) == b"", "closed stream still returned data")
    except ConnectionResetError:
        pass


def positive(address, name, port=PORT):
    with tls(address, name, port) as conn:
        echo(conn)


def mac_fixture():
    # Python's TLS server handles each connection in its own thread, so the idle TLS session and the
    # streaming session can both handshake on the same route. Like `openssl s_server -rev`, it answers
    # each line reversed. (s_server cannot listen on a Unix socket on macOS.)
    openssl = os.environ.get("OPENSSL", "openssl")
    with tempfile.TemporaryDirectory(prefix="b347-mac-") as directory, ExitStack() as stack:
        key = Path(directory) / "key.pem"
        cert = Path(directory) / "cert.pem"
        run(openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj",
            "/CN=probe.example.net", "-keyout", str(key), "-out", str(cert))
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)

        class Reverse(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.settimeout(70)
                try:
                    with context.wrap_socket(self.request, server_side=True) as conn:
                        pending = b""
                        while chunk := conn.recv(16384):
                            *lines, pending = (pending + chunk).split(b"\n")
                            for line in lines:
                                conn.sendall(line[::-1] + b"\n")
                except OSError:
                    pass  # Closed routes, refusals and idle timeouts end sessions abruptly.

        for port in (20443, 20444):
            server = stack.enter_context(socketserver.ThreadingTCPServer(("127.0.0.1", port), Reverse))
            server.daemon_threads = True
            threading.Thread(target=server.serve_forever, daemon=True).start()
            stack.callback(server.shutdown)
        print("Mac TLS fixtures are listening on 127.0.0.1 ports 20443 and 20444.", flush=True)
        print("In another Mac terminal, hold both forwards open with the disposable tunnel-test key.", flush=True)
        print("ssh -N -o ExitOnForwardFailure=yes -i /path/to/test-key "
              "-R 127.0.0.1:20099:127.0.0.1:20443 -R 127.0.0.1:20097:127.0.0.1:20444 "
              "tunnel-test@server.example.net", flush=True)
        threading.Event().wait()


class Acceptance:
    def __init__(self):
        require(os.geteuid() == 0, "Run the server phase as root.")
        self.cli = runpy.run_path(PROGRAM)
        self.server = self.cli["Server"]()
        machines = self.server.machines()
        require("tunnel-test" in machines, "Declare the tunnel-test fixture account first.")
        routes = self.server.routes()
        for name, route in routes.items():
            require(name in FIXTURES and route.account == "tunnel-test" and route.port == FIXTURES[name],
                    "Use a dedicated acceptance front with only the two fixture routes.")
        self.zone = self.server.zone()

    def names(self):
        routes = self.server.routes()
        return {name: routes[name].hostname(self.zone) for name in FIXTURES}

    def front(self, *argv, code=0):
        return run(PROGRAM, *argv, code=code)

    def expect_off(self, name=None, locked=False):
        start = time.monotonic()
        output = self.front("off", *([name] if name else []), code=2 if locked else 0)
        print(output)
        wanted = "CLOSED (verified): all routes; the front is locked" if locked else "CLOSED (verified)"
        require(output.splitlines()[0] == wanted, "wrong off outcome")
        return time.monotonic() - start

    def tunnel_up(self):
        require(set(map(str, FIXTURES.values())) <= self.server.listeners(), "both test tunnel ports must listen")

    def check_forwards(self):
        self.tunnel_up()
        names = self.names()
        for service, port in FIXTURES.items():
            positive("127.0.0.1", names[service], port)

    def both_on(self):
        self.tunnel_up()
        for name in FIXTURES:
            self.front("on", name)
            positive("127.0.0.1", self.names()[name])

    def outside(self, state):
        args = ["bash", "home-front/acceptance-front.sh", "outside", state, *self.names().values()]
        print("On the Mac connected to the phone hotspot, run in a checkout of the repository.")
        print("Append all expected private Caddy site URLs to this command.")
        print(shlex.join(args) + " <Caddy-URL> [<Caddy-URL> ...]")

    def start_checkpoint(self, next_phase):
        self.cli["File"](f"{next_phase} {BOOT.read_text()}".encode(), 0o600, (0, 0)).write(CHECKPOINT)
        print(f"Reboot the server, reconnect the Mac tunnel when needed, then run the {next_phase} phase.")

    def require_reboot(self, phase):
        require(CHECKPOINT.exists(), f"Run the corresponding preparation phase before {phase}.")
        expected, boot = CHECKPOINT.read_text().split()
        require(expected == phase and boot != BOOT.read_text().strip(), f"Reboot before {phase}.")

    def prepare(self):
        self.tunnel_up()
        for name, port in FIXTURES.items():
            if name not in self.server.routes():
                print(self.front("route", name, "tunnel-test", str(port)))
        self.both_on()
        refusal("127.0.0.1", f"{UNKNOWN}.{self.zone}")
        refusal("127.0.0.1", None)
        self.outside("both")

    def normal(self):
        self.both_on()
        names = self.names()
        with tls("127.0.0.1", names["probe"]) as idle, tls("127.0.0.1", names["probe"]) as stream:
            with streaming(stream) as transfers:
                require(self.expect_off("probe") < 10, "normal off took at least 10 seconds")
                require(transfers.result(timeout=7), "streaming client did not close")
            ended(idle)
        refusal("127.0.0.1", names["probe"])
        positive("127.0.0.1", names["probe2"])
        self.tunnel_up()
        self.front("on", "probe")
        positive("127.0.0.1", names["probe"])

        self.expect_off("probe2")
        with tls("127.0.0.1", names["probe"]) as stream:
            echo(stream)
            self.front("on", "probe2")
            echo(stream)  # Prove reload left the earlier worker's stream intact.
            positive("127.0.0.1", names["probe2"])
            self.expect_off("probe")
            ended(stream)
        refusal("127.0.0.1", names["probe"])
        positive("127.0.0.1", names["probe2"])
        self.outside("second")

    def stale_prepare(self):
        self.both_on()
        label = self.server.routes()["probe"].label
        with self.server.locked():
            previous = ROUTES.read_text()
            contents = "".join(
                line.rsplit("on", 1)[0] + "off\n" if line.startswith(label + " ") else line
                for line in previous.splitlines(keepends=True)
            )
            require(contents != previous and " probe\n" in MAP.read_text(), "the stale render fixture is missing")
            self.cli["File"](contents.encode(), 0o600, (0, 0)).write(ROUTES)
        self.start_checkpoint("stale-check")

    def check_second(self):
        self.check_forwards()
        positive("127.0.0.1", self.names()["probe2"])
        refusal("127.0.0.1", self.names()["probe"])
        require(" probe\n" not in MAP.read_text() and "\nbackend probe\n" not in CFG.read_text(),
                "the rendered files still include probe")
        self.outside("second")

    def stale_check(self):
        self.require_reboot("stale-check")
        self.check_second()
        CHECKPOINT.unlink()

    @contextmanager
    def render_switch(self, mode):
        drop_in = Path(self.cli["FRONT_ACCEPTANCE_DROP_IN"])
        drop_in.parent.mkdir(parents=True, exist_ok=True)
        require(not drop_in.exists(), f"Remove the previous acceptance drop-in {drop_in} first.")
        # The shim must be executable, and Debian mounts /run noexec. If a run is interrupted, the directory
        # stays inert: only the PATH drop-in in /run points at it, and a reboot removes that.
        with tempfile.TemporaryDirectory(prefix="home-front-acceptance-", dir="/root") as private:
            private = Path(private)
            wrapper = private / "render.py"
            wrapper.write_text(f"""
from pathlib import Path
import runpy
import signal
import sys
import time

cli = runpy.run_path({PROGRAM!r})
server = cli["Server"]
read = server.front_files
fixture = Path({str(private)!r})

def render(self, strict=False):
    files = read(self, strict)
    if {mode!r} == "fail":
        raise cli["Error"]("acceptance: injected render failure")
    if not (fixture / "paused").exists():
        # A replacement restart can stop the pre-start hook. Hold it until the test sees the manager's job.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        (fixture / "paused").write_bytes(files[{str(MAP)!r}].data)
        deadline = time.monotonic() + 20
        while not (fixture / "release").exists():
            if time.monotonic() > deadline:
                raise cli["Error"]("acceptance: render hold timed out")
            time.sleep(0.02)
    return files

server.front_files = render
sys.argv = [{PROGRAM!r}, "render", "--for-start"]
sys.exit(cli["main"]())
""")
            # home-front uses /usr/bin/env python3. Inject the fixture inside this unit and keep ExecStartPre intact.
            shim = private / "python3"
            shim.write_text(f"""#!/bin/sh
if [ "$1" = {shlex.quote(PROGRAM)} ] && [ "$2" = render ] && [ "$3" = --for-start ]; then
    exec /usr/bin/python3 {shlex.quote(str(wrapper))}
fi
exec /usr/bin/python3 "$@"
""")
            shim.chmod(0o700)
            run(str(shim), "-c", "pass")  # Fail clearly if the shim cannot run.
            previous = os.environ.get("HOME_FRONT_ACCEPTANCE")
            try:
                drop_in.write_text(f"[Service]\nEnvironment=PATH={private}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin\n")
                run("systemctl", "daemon-reload")
                os.environ["HOME_FRONT_ACCEPTANCE"] = "1"
                require(self.server.hooks_effective(), "HAProxy's managed start and reload hooks are not effective")
                yield private
            finally:
                if previous is None:
                    os.environ.pop("HOME_FRONT_ACCEPTANCE", None)
                else:
                    os.environ["HOME_FRONT_ACCEPTANCE"] = previous
                (private / "release").touch()
                drop_in.unlink()
                run("systemctl", "daemon-reload")

    def jobs(self):
        output = run("systemctl", "list-jobs", "--no-legend", "--no-pager", UNIT)
        return [fields[2:4] for line in output.splitlines()
                if len(fields := line.split()) >= 4 and fields[1] == UNIT]

    def overlap(self):
        self.both_on()
        with self.render_switch("pause") as private:
            with subprocess.Popen(["systemctl", "restart", UNIT]) as original, ExitStack() as stack:
                stack.callback((private / "release").touch)
                paused = private / "paused"
                wait_for(lambda: paused.exists() and b" probe\n" in paused.read_bytes(),
                         "manual restart did not hold a snapshot with probe on")
                require(self.jobs() == [["start", "running"]],
                        "systemd did not show the held HAProxy start job")
                off = stack.enter_context(subprocess.Popen([PROGRAM, "off", "probe"], text=True, stdout=subprocess.PIPE))
                stack.callback((private / "release").touch)
                wait_for(lambda: self.server.routes()["probe"].state == "off", "off did not write while start was paused")
                wait_for(lambda: any(job[0] == "restart" for job in self.jobs()),
                         "systemd did not show the second HAProxy restart while the render was paused")
                (private / "release").touch()
                output, _ = off.communicate(timeout=15)
                require(off.returncode == 0 and output.strip() == "CLOSED (verified)", output or "off failed")
                print(output.strip())
                original.wait(timeout=15)
        self.check_second()

    def fault(self, mode):
        self.both_on()
        names = self.names()
        with tls("127.0.0.1", names["probe"]) as stream, ExitStack() as stack:
            echo(stream)
            if mode == "render":
                stack.enter_context(self.render_switch("fail"))
            else:
                run("chattr", "+i", str(ROUTES))
                stack.callback(run, "chattr", "-i", str(ROUTES))
            self.expect_off(None if mode == "write-all" else "probe", locked=True)
            ended(stream)
            self.expect_off("probe2", locked=True)
        self.tunnel_up()
        self.start_checkpoint("fault-check")

    def fault_check(self):
        self.require_reboot("fault-check")
        require(LOCK.is_file() and run("systemctl", "is-enabled", UNIT, code=1) == "disabled",
                "locked front is not disabled after reboot")
        require("8443" not in self.server.listeners(), "port 8443 is listening after the locked reboot")
        require("front is locked" in self.front("on", "probe2", code=1), "on did not refuse the locked front")
        self.check_forwards()
        run("systemctl", "start", UNIT)
        require(run("systemctl", "is-active", UNIT) == "active", "manual locked start failed")
        for name in self.names().values():
            refusal("127.0.0.1", name)
            refusal("::1", name)
        print(self.front("reconcile"))
        require(not LOCK.exists() and all(r.state == "off" for r in self.server.routes().values()),
                "reconcile did not persist every route off")
        require(run("systemctl", "is-enabled", UNIT) == "enabled"
                and run("systemctl", "is-active", UNIT) == "active", "reconciled front is not enabled and active")
        for name in self.names().values():
            refusal("127.0.0.1", name)
        self.front("on", "probe2")
        self.check_second()
        self.start_checkpoint("post-reboot")

    def post_reboot(self):
        self.require_reboot("post-reboot")
        self.check_second()
        run("systemctl", "is-active", "caddy.service")
        CHECKPOINT.unlink()


def main():
    parser = argparse.ArgumentParser(description="Run a B347 server-front acceptance phase.")
    phases = parser.add_subparsers(dest="phase", required=True)
    for phase in ("mac-fixture", "prepare", "normal", "stale-prepare", "stale-check", "overlap",
                  "fault-check", "post-reboot"):
        phases.add_parser(phase)
    phases.add_parser("fault").add_argument("mode", choices=("write", "render", "write-all"))
    outside = phases.add_parser("outside")
    outside.add_argument("state", choices=("both", "second"))
    outside.add_argument("probe")
    outside.add_argument("probe2")
    outside.add_argument("caddy_url", nargs="+")
    args = parser.parse_args()
    if args.phase == "mac-fixture":
        mac_fixture()
    elif args.phase == "outside":
        unknown = UNKNOWN + "." + args.probe.partition(".")[2]
        require(unknown not in (args.probe, args.probe2), "choose a different unknown fixture label")
        positive(args.probe2, args.probe2)
        if args.state == "both":
            positive(args.probe, args.probe)
        else:
            refusal(args.probe, args.probe)
        refusal(args.probe2, unknown)
        refusal(args.probe2, None)
        for url in args.caddy_url:
            run("curl", "-fsSI", "--proto", "=https", "--max-time", "10", "--", url)
        print("Hotspot checks passed.")
    else:
        acceptance = Acceptance()
        if args.phase == "fault":
            acceptance.fault(args.mode)
        else:
            getattr(acceptance, args.phase.replace("-", "_"))()


try:
    main()
except KeyboardInterrupt:
    raise SystemExit(130) from None
PY
