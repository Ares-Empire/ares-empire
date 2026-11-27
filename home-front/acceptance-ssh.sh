#!/usr/bin/env bash
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec python3 - "$here/home-front" "$@" <<'PY'
import argparse
from contextlib import ExitStack
import os
from pathlib import Path
import re
import runpy
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time


class Failure(Exception):
    pass


def require(condition, message):
    if not condition:
        raise Failure(message)


def wait_for(predicate, message, deadline):
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.025)
    raise Failure(message)


def stop(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    if proc.stdin:
        proc.stdin.close()


GREETING = b"home-front acceptance\n"
AUTHENTICATED = "Authenticated to "
REVERSE_REFUSED = "remote port forwarding failed for listen port"


class Greeting(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.sendall(GREETING)
        while self.request.recv(1024):
            pass


class Fixture(socketserver.ThreadingTCPServer):
    daemon_threads = True


def acceptance(args, policy, stack):
    server = policy["Server"](os.environ.get("HOME_FRONT_ROOT", "/"), os.environ.get("HOME_FRONT_RUNNER"))
    require(os.geteuid() == 0 or server.root != Path("/"), "run the server acceptance as root")
    require(1 <= args.port <= 65535, "invalid SSH port")
    home_front = str(server.path(policy["PROGRAM"]))
    config = server.path(policy["CONFIG"])
    source = "127.0.0.1"
    machine_specs = {
        "tunnel-test": ("listen", {20097, 20099, 20199}),
        "jump-test": ("open", {20199}),
    }
    machines = server.machines()
    for name, (kind, ports) in machine_specs.items():
        machine = machines.get(name)
        require(machine and machine.kind == kind and set(machine.ports) == ports,
                f"{name}: declare the P1a fixture in /etc/home-front/machines")
        if server.lookup("passwd", name) is not None:
            require(server.run("pgrep", "-u", name, allowed=(0, 1)).returncode == 1,
                    f"{name} already has processes")
    require(not server.listeners().intersection({"20097", "20098", "20099", "20199"}),
            "a server fixture port is already listening")
    scratch_parent = server.storage(policy["STATE"], 0o700)
    scratch = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="acceptance-", dir=scratch_parent)))

    public = {}
    for name, identity in zip(machine_specs, (args.tunnel_key, args.jump_key)):
        public[name] = scratch / f"{name}.pub"
        public[name].write_text(server.run("ssh-keygen", "-y", "-P", "", "-f", str(identity)).stdout)
    keys = {name: path.resolve() for name, path in zip(machine_specs, (args.tunnel_key, args.jump_key))}
    sources = server.sources()
    baseline = server.root_baseline(sources)

    def manage(*argv, outcome=None):
        try:
            result = server.run(home_front, *argv)
        finally:
            if argv[0] in ("add-machine", "render"):
                server.check_admin(config, baseline)
        print(result.stdout.rstrip(), flush=True)
        if outcome:
            require(result.stdout.splitlines()[-1] == outcome, f"{argv[0]}: missing {outcome!r}")
        return result.stdout

    def ssh(name, *argv):
        command = [
            "ssh", "-F", os.devnull, "-4", "-vv", "-T", "-b", source, "-p", str(args.port), "-l", name,
            "-o", "BatchMode=yes", "-o", "ConnectTimeout=3", "-o", "ConnectionAttempts=1",
            "-o", "ControlMaster=no", "-o", "StrictHostKeyChecking=yes",
            "-o", "GlobalKnownHostsFile=" + os.devnull, "-o", "UserKnownHostsFile=" + str(args.known_hosts),
            "-o", "HostKeyAlias=server.example.net", "-o", "IdentitiesOnly=yes", "-o", "IdentityAgent=none",
            "-o", "PreferredAuthentications=publickey", "-i", str(keys[name]), *argv, source,
        ]
        return [server.runner, *command] if server.runner else command

    def start(name, *argv, remote_command=()):
        stdout = tempfile.TemporaryFile(dir=scratch)
        stderr = tempfile.TemporaryFile(dir=scratch)
        stack.callback(stdout.close)
        stack.callback(stderr.close)
        proc = subprocess.Popen([*ssh(name, *argv), *remote_command], stdin=subprocess.PIPE,
                                stdout=stdout, stderr=stderr, env={**os.environ, "LC_ALL": "C"})
        stack.callback(stop, proc)
        return proc, stdout, stderr

    def output(file):
        # pread leaves the child process's file offset alone.
        return os.pread(file.fileno(), 131072, 0).decode(errors="replace")

    def expect_failure(name, *argv, diagnostic, remote_command=(), authenticated=True):
        proc, _, stderr = start(name, *argv, remote_command=remote_command)
        require(proc.wait(timeout=5) != 0, f"{name}: prohibited SSH operation succeeded")
        log = output(stderr)
        require(diagnostic in log and (not authenticated or AUTHENTICATED in log),
                f"{name}: expected {diagnostic!r}: {log}")

    def authenticated(session, message):
        proc, _, stderr = session
        wait_for(lambda: AUTHENTICATED in output(stderr) or proc.poll() is not None, message, time.monotonic() + 4)
        require(AUTHENTICATED in output(stderr) and proc.poll() is None, f"{message}: {output(stderr)}")

    def listener_rows(port):
        result = server.run("ss", "-H", "-ltnp", f"sport = :{port}").stdout
        return [line for line in result.splitlines() if line.strip()]

    def verify_owner(port):
        listeners = listener_rows(port)
        require(len(listeners) == 1, f"expected one listener on port {port}: {listeners}")
        fields = listeners[0].split()
        pids = re.findall(r'\("sshd(?:-session|-auth)?",pid=(\d+)', listeners[0])
        require(fields[3] == f"127.0.0.1:{port}" and pids,
                f"expected an sshd loopback listener on port {port}: {listeners[0]}")
        owned = server.run("pgrep", "-u", "tunnel-test", allowed=(0, 1)).stdout.split()
        require(set(pids).intersection(owned),
                f"port {port} has no owner running as tunnel-test: {listeners[0]}")
        return pids

    for name in machine_specs:
        manage("add-machine", name, str(public[name]))
    reload_log = manage("render")
    before = next((line.removeprefix("Saved root effective settings in ") for line in reload_log.splitlines()
                   if line.startswith("Saved root effective settings in ")), "")
    require(bool(before), "the reload guard did not report a baseline")
    for number, (host, address) in enumerate(dict.fromkeys(sources), 1):
        snapshot = Path(before) / f"{number:03d}-{host}-{address}.conf"
        require(snapshot.read_text() == baseline[(host, address)],
                f"live root settings differ from {snapshot}")
    for machine in machines.values():
        if machine.name in machine_specs or server.lookup("passwd", machine.name) is not None:
            server.check_machine(config, machine, sources[0])
    print("PASS: root snapshots and all three effective settings checks", flush=True)

    trouble = "-o", "ExitOnForwardFailure=yes"
    require(not listener_rows(20199), "jump reverse-bind test port 20199 is in use")
    expect_failure("jump-test", "-N", *trouble, "-R", "127.0.0.1:20199:127.0.0.1:9", diagnostic=REVERSE_REFUSED)
    require(not listener_rows(20199), "jump created a reverse listener on an allowed destination port")

    for bind, port in (("127.0.0.1", 20098), ("0.0.0.0", 20099)):
        expect_failure("tunnel-test", "-N", *trouble, "-R", f"{bind}:{port}:127.0.0.1:9",
                       diagnostic=REVERSE_REFUSED)
        require(not listener_rows(port), f"forbidden bind left a listener on {port}")
    unix_dir = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="home-front-", dir=server.path("/run"))))
    tunnel_uid = server.lookup("passwd", "tunnel-test")[2]
    server.run("chown", tunnel_uid, str(unix_dir))
    server.run("runuser", "-u", "tunnel-test", "--", "test", "-w", str(unix_dir))
    unix_path = unix_dir / "forbidden.sock"
    expect_failure("tunnel-test", "-N", *trouble, "-R", f"{unix_path}:127.0.0.1:9",
                   diagnostic="remote port forwarding failed")
    require(not os.path.lexists(unix_path), "forbidden Unix socket was created")

    fixture = stack.enter_context(Fixture((source, 0), Greeting))
    threading.Thread(target=fixture.serve_forever, daemon=True).start()
    stack.callback(fixture.shutdown)
    fixture_port = fixture.server_address[1]
    require(fixture_port not in {9999, 20097, 20098, 20099, 20199}, "fixture chose a reserved port; rerun")
    collision = "-R", "127.0.0.1:20099:127.0.0.1:9"
    holder1 = start("tunnel-test", "-N", *trouble, *collision, "-R", f"127.0.0.1:20199:127.0.0.1:{fixture_port}")
    authenticated(holder1, "holder 1 did not authenticate")
    wait_for(lambda: listener_rows(20099) and listener_rows(20199), "holder 1 did not bind both ports",
             time.monotonic() + 4)
    owners = {port: verify_owner(port) for port in (20099, 20199)}
    expect_failure("tunnel-test", "-N", *trouble, *collision, diagnostic=f"{REVERSE_REFUSED} 20099")
    holder2 = start("tunnel-test", "-N", "-o", "ExitOnForwardFailure=no", *collision)
    wait_for(lambda: f"{REVERSE_REFUSED} 20099" in output(holder2[2]), "holder 2 did not report the collision",
             time.monotonic() + 4)
    authenticated(holder2, "holder 2 did not stay logged in")
    require(all(verify_owner(port) == pids for port, pids in owners.items()), "holder 1 lost a listener")
    print("PASS: reverse binds, forbidden binds and both holder behaviors", flush=True)

    require(not listener_rows(9999), "local-forward test port 9999 is in use")
    local = start("tunnel-test", "-N", *trouble, "-L", "127.0.0.1:9999:127.0.0.1:22")
    authenticated(local, "local-forward client did not authenticate")
    wait_for(lambda: listener_rows(9999), "local SSH client did not bind port 9999", time.monotonic() + 3)
    with socket.create_connection((source, 9999), timeout=3) as channel:
        try:
            banner = channel.recv(256)
        except (TimeoutError, ConnectionResetError):
            banner = b""
        require(not banner, "the tunnel credential received data from the server's SSH port")
    wait_for(lambda: "administratively prohibited" in output(local[2]), "local forward was not denied",
             time.monotonic() + 3)
    stop(local[0])

    jump = start("jump-test", "-W", "127.0.0.1:20199")
    wait_for(lambda: GREETING.decode() in output(jump[1]), "jump did not read the test listener's greeting",
             time.monotonic() + 4)
    for port in (22, 20099):
        expect_failure("jump-test", "-W", f"127.0.0.1:{port}", diagnostic="administratively prohibited")
    expect_failure("jump-test", "-N", *trouble, "-R", "127.0.0.1:20098:127.0.0.1:9", diagnostic=REVERSE_REFUSED)
    require(not listener_rows(20098), "jump created a reverse listener")
    for name in machine_specs:
        expect_failure(name, diagnostic="open failed")
        expect_failure(name, diagnostic="open failed", remote_command=("true",))
    print("PASS: tunnel local forward, jump limits, shell and command checks", flush=True)

    journal = ("journalctl", "--no-pager", "-u", policy["SERVICE"], "-o", "cat")
    cursor_lines = server.run(*journal, "-n", "1", "--show-cursor").stdout.splitlines()
    cursor = next((line.removeprefix("-- cursor: ") for line in cursor_lines if line.startswith("-- cursor: ")), "")
    require(bool(cursor), "STOP: could not locate the SSH journal cursor for the reconnect check")
    issue = None
    try:
        for attempt in range(10):
            started = time.monotonic()
            expect_failure("tunnel-test", "-N", *trouble, *collision, diagnostic=f"{REVERSE_REFUSED} 20099")
            print(f"Reconnect {attempt + 1}/10 authenticated and hit the occupied port", flush=True)
            if attempt < 9:
                time.sleep(max(0, started + 2 - time.monotonic()))
    except (Failure, subprocess.SubprocessError) as error:
        issue = f"reconnect loop: {error}"
    try:
        fresh = start("tunnel-test", "-N")
        authenticated(fresh, "fresh login from the reconnect source failed")
        stop(fresh[0])
    except (Failure, subprocess.SubprocessError) as error:
        issue = f"{issue}; {error}" if issue else str(error)
    time.sleep(0.25)
    journal_lines = server.run(*journal, "--after-cursor", cursor).stdout.splitlines()
    penalties = [line for line in journal_lines
                 if re.search(r"penalt|refus.*connection|drop connection", line, re.I)
                 and re.search(r"(?<![0-9.])127\.0\.0\.1(?![0-9.])", line)]
    if penalties:
        print("STOP: sshd logged a possible source penalty during the reconnect check:", flush=True)
        for line in penalties:
            print(line, flush=True)
        if issue:
            print(issue, flush=True)
        return 2
    require(issue is None, f"STOP: no source penalty seen in the SSH journal, but {issue}")
    print("PASS: 10 reconnects, fresh login succeeded, and the SSH journal shows no source penalty", flush=True)

    require(jump[0].poll() is None, "jump stream closed before its revocation")
    manage("remove-machine", "jump-test", outcome="CLOSED (verified)")
    jump[0].wait(timeout=2)
    require(verify_owner(20199) == owners[20199], "jump revocation changed the tunnel's listener")

    require(holder1[0].poll() is None and holder2[0].poll() is None, "holders must both be logged in for revocation")
    ended = threading.Event()
    deadline = time.monotonic() + 2

    def watch_holders():
        while time.monotonic() < deadline:
            if holder1[0].poll() is not None and holder2[0].poll() is not None:
                ended.set()
                return
            time.sleep(0.01)

    watcher = threading.Thread(target=watch_holders, daemon=True)
    watcher.start()
    manage("remove-machine", "tunnel-test", outcome="CLOSED (verified)")
    watcher.join()
    require(ended.is_set(), "both holders must end within two seconds of revocation")
    require(not any(listener_rows(port) for port in (20097, 20099, 20199)), "tunnel listeners survived removal")
    expect_failure("tunnel-test", "-N", diagnostic="Permission denied", authenticated=False)
    print("PASS: jump and tunnel revocations verified", flush=True)

    for name in machine_specs:
        manage("add-machine", name, str(public[name]))
    print("PASS: both fixture accounts re-added", flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Run the home-front SSH acceptance on the server.")
    parser.add_argument("tunnel_key", type=Path)
    parser.add_argument("jump_key", type=Path)
    parser.add_argument("known_hosts", type=Path)
    parser.add_argument("--port", type=int, default=22)
    args = parser.parse_args(sys.argv[2:])
    policy = runpy.run_path(sys.argv[1])
    try:
        with ExitStack() as stack:
            return acceptance(args, policy, stack)
    except (Failure, policy["Error"], OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"SSH acceptance failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
PY
