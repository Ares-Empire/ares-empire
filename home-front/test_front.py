"""Test the server front with scratch files and a stateful model of the systemd unit."""

import fcntl
import json
import os
from pathlib import Path
import runpy
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
PROGRAM = HERE / "home-front"
POLICY = runpy.run_path(str(PROGRAM))
ROUTES, LOCK, CONFIG, MAP = (POLICY[key].lstrip("/") for key in
                              ("ROUTES", "FRONT_LOCK", "HAPROXY_CONFIG", "HAPROXY_MAP"))
CGROUP = POLICY["FRONT_CGROUP"]
CGROUP_DIRECTORY = "sys/fs/cgroup" + CGROUP
DROP_IN = POLICY["FRONT_DROP_IN"].lstrip("/")
ACCEPTANCE_DROP_IN = POLICY["FRONT_ACCEPTANCE_DROP_IN"].lstrip("/")
LOCAL_UNIT = POLICY["FRONT_LOCAL_UNIT"].lstrip("/")
DROP_IN_PATH = HERE.parent / "deploy/systemd/haproxy-home-front.conf"
PASSWD = (
    "root:x:0:0:root:/root:/bin/bash\n"
    "tunnel-test:x:901:900:home-front listen 20099 20199:/nonexistent:/usr/sbin/nologin\n"
    "other-test:x:902:900:home-front listen 20097:/nonexistent:/usr/sbin/nologin\n"
    "jump-test:x:903:900:home-front open 20199:/nonexistent:/usr/sbin/nologin\n"
)
SHADOW = "".join(f"{name}:!:19000:0:99999:7:::\n" for name in ("tunnel-test", "other-test", "jump-test"))
GROUP = "hometunnel:x:900:\n"
FIRST = "abcdefghijklmnop"
SECOND = "qrstuvwxyz234567"
HOST = FIRST + ".home.example.net"
HOST2 = SECOND + ".home.example.net"
FIXTURE = f"{FIRST} tunnel-test 20099 probe on\n{SECOND} other-test 20097 probe2 on\n"
LOCKED = "CLOSED (verified): all routes; the front is locked"
UNCONFIRMED = "REVOCATION UNCONFIRMED"
EXEC_QUERY = ["-p", "ExecStartPre", "-p", "ExecStart", "-p", "ExecReload", "haproxy.service"]
PATH_QUERY = ["-p", "FragmentPath", "-p", "DropInPaths", "haproxy.service"]
RELOAD_QUERY = ["-p", "NeedDaemonReload", "haproxy.service"]
LOAD_QUERY = ["-p", "LoadState", "haproxy.service"]
EXEC_SHOW = """\
ExecStartPre={ path=/usr/local/sbin/home-front ; argv[]=/usr/local/sbin/home-front render --for-start ; ignore_errors=no ; start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0 }
ExecStart={ path=/usr/sbin/haproxy ; argv[]=/usr/sbin/haproxy -Ws -f /etc/haproxy/haproxy.cfg -p /run/haproxy.pid ; ignore_errors=no ; start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0 }
ExecReload={ path=/usr/local/sbin/home-front ; argv[]=/usr/local/sbin/home-front render --for-reload ; ignore_errors=no ; start_time=[Fri 2026-11-27 03:06:52 CET] ; stop_time=[Fri 2026-11-27 03:06:52 CET] ; pid=3886025 ; code=exited ; status=0 }
ExecReload={ path=/usr/local/sbin/home-front ; argv[]=/usr/local/sbin/home-front _reload-front ${MAINPID} ; ignore_errors=no ; start_time=[Fri 2026-11-27 03:06:52 CET] ; stop_time=[Fri 2026-11-27 03:06:52 CET] ; pid=3886028 ; code=exited ; status=0 }
"""


class Unit:
    def __init__(self):
        self.root = Path(os.environ["HOME_FRONT_ROOT"])
        self.mode = set(os.environ.get("FRONT_FAULTS", "").split(","))
        self.package_present = "missing-package" not in self.mode
        self.state = self.root / "unit-state"
        if self.state.exists():
            self.active, self.enabled, self.serial = json.loads(self.state.read_text())
        else:
            self.active, self.enabled, self.serial = False, False, 10
        self.cgroup = self.root / CGROUP_DIRECTORY / "cgroup.procs"
        self.master = self.root / "unit-master"
        self.worker = self.root / "unit-worker"
        self.mapping = self.root / "unit-map"
        self.start_limit = self.root / "unit-start-limit-hit"
        self.loaded_drop_in = self.root / "unit-drop-in"
        self.loaded_paths = self.root / "unit-paths"

    def processes(self):
        return self.cgroup.read_text().split() if self.cgroup.exists() else []

    def save(self, pids=None):
        if pids:
            self.cgroup.parent.mkdir(exist_ok=True)
            self.cgroup.write_text("\n".join(pids))
        elif pids == []:
            stray = self.cgroup.parent / "stray/cgroup.procs"
            if stray.exists() or "stray-cgroup" in self.mode:
                stray.parent.mkdir(parents=True, exist_ok=True)
                self.cgroup.write_text("")
                if not stray.exists():
                    stray.write_text(self.spawn())
            elif self.cgroup.parent.exists():
                shutil.rmtree(self.cgroup.parent)
        snapshot = self.state.with_name(f".unit-state-{os.getpid()}")
        snapshot.write_text(json.dumps([self.active, self.enabled, self.serial]))
        snapshot.replace(self.state)

    def spawn(self):
        self.serial += 1
        pid = str(self.serial)
        clock = getattr(time, "CLOCK_BOOTTIME", time.CLOCK_MONOTONIC)
        ticks = time.clock_gettime_ns(clock) * os.sysconf("SC_CLK_TCK") // 10**9
        stat = self.root / "proc" / pid / "stat"
        stat.parent.mkdir(parents=True, exist_ok=True)
        stat.write_text(f"{pid} (fake worker) " + " ".join(["S"] + ["0"] * 18 + [str(ticks)]))
        return pid

    def hook(self, *args):
        program = os.environ.get("TEST_PROGRAM", str(PROGRAM))
        rendering = args[0] == "render"
        if "pause" in self.mode and rendering:
            argv = [sys.executable, "-c", INJECT, program, *args]
        else:
            argv = [sys.executable, program, *args]
        env = {**os.environ, "FRONT_TEST_RENDER": "1" if rendering else ""}
        shadow = self.root / "etc/shadow"
        unreadable = rendering and "hook-lookup" in self.mode
        if unreadable:
            shadow.chmod(0)
        try:
            result = subprocess.run(argv, env=env, timeout=12, capture_output=True, text=True)
        finally:
            if unreadable:
                shadow.chmod(0o600)
        with (self.root / "unit-journal").open("a") as journal:
            journal.write(result.stdout + result.stderr)
        if result.returncode:
            print("Job for haproxy.service failed. See the unit journal for details.", file=sys.stderr)
        return result.returncode

    def exec_commands(self, property_name):
        if self.loaded_drop_in.exists():
            prefix = property_name + "="
            return [line[len(prefix):] for line in self.loaded_drop_in.read_text().splitlines()
                    if line.startswith(prefix) and line != prefix]
        # The vendor unit never invokes home-front.
        return {
            "ExecStartPre": ["/usr/sbin/haproxy -f /etc/haproxy/haproxy.cfg -c -q"],
            "ExecStart": ["/usr/sbin/haproxy -Ws -f /etc/haproxy/haproxy.cfg -p /run/haproxy.pid $EXTRAOPTS"],
            "ExecReload": ["/bin/kill -USR2 $MAINPID"],
        }[property_name]

    def disk_unit_paths(self):
        directories = ("etc/systemd/system", "run/systemd/system", "usr/local/lib/systemd/system",
                       "usr/lib/systemd/system")
        fragments = [f"{directory}/haproxy.service" for directory in directories]
        vendor_fragment = POLICY["FRONT_FRAGMENT"] if self.package_present else ""
        fragment = next((f"/{name}" for name in fragments if os.path.lexists(self.root / name)), vendor_fragment)
        if not fragment:
            return "FragmentPath=\nDropInPaths=\n"
        drop_ins = ["/" + str(path.relative_to(self.root)) for directory in directories
                    for path in (self.root / directory / "haproxy.service.d").glob("*.conf")]
        drop_ins.sort(key=lambda path: Path(path).name)
        return f"FragmentPath={fragment}\nDropInPaths={' '.join(drop_ins)}\n"

    def effective_unit_paths(self):
        if self.loaded_paths.exists():
            return self.loaded_paths.read_text()
        managed = POLICY["FRONT_DROP_IN"] if self.loaded_drop_in.exists() else ""
        return f"FragmentPath={POLICY['FRONT_FRAGMENT']}\nDropInPaths={managed}\n"

    def masked(self):
        local = self.root / LOCAL_UNIT
        return (f"FragmentPath=/{LOCAL_UNIT}\n" in self.effective_unit_paths()
                and local.is_symlink() and local.readlink() == Path("/dev/null"))

    def start(self, *, restart=False):
        if self.masked():
            print("Unit haproxy.service is masked.", file=sys.stderr)
            return 1
        if not self.package_present:
            return 1
        if self.start_limit.exists():
            print("HAProxy start request repeated too quickly (start-limit-hit).", file=sys.stderr)
            return 1
        if self.active and not restart:
            return 0
        old = self.processes()
        self.active = False
        self.save([])
        if "restart" in self.mode:
            return 1
        if POLICY["FRONT_COMMANDS"]["ExecStartPre"][0] in self.exec_commands("ExecStartPre") and self.hook("render", "--for-start"):
            if "start-limit-on-render-failure" in self.mode:
                # Model the limit after Debian's Restart=always has retried the same failed start.
                self.start_limit.touch()
            return 1
        pids = [self.spawn(), self.spawn()]
        self.master.write_text(pids[0])
        self.worker.write_text(pids[1])
        (self.root / "unit-config").write_bytes((self.root / CONFIG).read_bytes())
        self.mapping.write_bytes((self.root / MAP).read_bytes())
        self.active = True
        self.save(pids + old if "old-worker" in self.mode else pids)
        return 0

    def systemctl(self, args):
        op, *flags = args
        if op == "show":
            if flags == ["-p", "Result", "haproxy.service"]:
                print("Result=start-limit-hit" if self.start_limit.exists() else "Result=success")
                return 0
            if flags == LOAD_QUERY:
                state = "loaded" if "FragmentPath=\n" not in self.effective_unit_paths() else "not-found"
                print(f"LoadState={'masked' if self.masked() else state}")
                return 0
            if flags == RELOAD_QUERY:
                fixture = self.root / "unit-reload-needed"
                stale = self.disk_unit_paths() != self.effective_unit_paths()
                needed = "yes" if stale else "no"
                if fixture.exists():
                    needed = fixture.read_text().strip()
                print(f"NeedDaemonReload={needed}")
                return 0
            if flags == PATH_QUERY:
                print(self.effective_unit_paths(), end="")
                return 0
            if flags == EXEC_QUERY:
                snapshot = self.root / "routes-at-hook-query"
                if "hooks-query" in self.mode or ("hooks-query-once" in self.mode and not snapshot.exists()):
                    snapshot.write_bytes((self.root / ROUTES).read_bytes())
                    return 1
                show = self.root / "unit-exec-show"
                if show.exists():
                    print(show.read_text(), end="")
                    return 0
                for property_name in flags[1:-1:2]:
                    for command in self.exec_commands(property_name):
                        print(f"{property_name}={{ path={shlex.split(command)[0]} ; argv[]={command} ; "
                              "ignore_errors=no ; start_time=[n/a] ; stop_time=[n/a] ; "
                              "pid=0 ; code=(null) ; status=0/0 }")
                return 0
            assert flags == ["--value", "-p", "ControlGroup", "haproxy.service"]
            print(CGROUP if self.active or self.processes() else "")
            return 0
        if op == "is-enabled":
            if self.masked():
                print("masked")
                return 1
            print("enabled" if self.enabled else "disabled")
            return 0 if self.enabled else 1
        if op == "is-active":
            print("failed" if self.start_limit.exists() else "active" if self.active else "inactive")
            return 0 if self.active else 3
        if op == "reset-failed":
            assert flags == ["haproxy.service"]
            self.start_limit.unlink(missing_ok=True)
            return 0
        if op == "restart":
            return self.start(restart=True)
        if op == "start":
            return self.start()
        if op == "reload":
            if not self.active or "reload" in self.mode:
                return 1
            if POLICY["FRONT_COMMANDS"]["ExecReload"][0] not in self.exec_commands("ExecReload"):
                return self.run("kill", ["-USR2", self.master.read_text()])
            return (self.hook("render", "--for-reload") or self.hook("_reload-front", self.master.read_text())
                    or int("post-reload" in self.mode))
        if op == "enable":
            assert flags in (["--now", "haproxy.service"], ["haproxy.service"])
            if self.masked():
                return 1
            if "override-on-enable" in self.mode:
                foreign = (self.root / ACCEPTANCE_DROP_IN).with_name("99-foreign.conf")
                foreign.parent.mkdir(parents=True, exist_ok=True)
                foreign.write_text("[Service]\nRestart=on-failure\n")
            self.enabled = "enable" not in self.mode
            self.save()
            self.systemctl(["daemon-reload"])
            return self.start() if "--now" in flags else 0
        if op == "stop":
            assert flags == ["haproxy.service"]
            if "stop" in self.mode:
                return 1
            self.active = False
            self.save([])
            return 0
        if op == "disable":
            assert flags in (["--now", "haproxy.service"], ["haproxy.service"])
            if "disable" in self.mode:
                return 1
            self.enabled = "still-enabled" in self.mode
            self.save()
            self.systemctl(["daemon-reload"])
            return self.systemctl(["stop", "haproxy.service"]) if "--now" in flags else 0
        if op == "kill":
            assert flags == ["-s", "KILL", "haproxy.service"]
            if "kill" in self.mode:
                print("injected kill failure", file=sys.stderr)
                return 1
            if not self.active and not self.processes():
                print("Failed to kill unit haproxy.service: Unit haproxy.service not loaded.", file=sys.stderr)
                return 1
            was_active = self.active
            self.active = False
            self.save([])
            return self.start() if was_active else 0  # Debian's unit has Restart=always.
        if op == "daemon-reload":
            drop_in = self.root / DROP_IN
            if drop_in.exists():
                contents = drop_in.read_bytes()
                if "override-hook" in self.mode:
                    contents = contents.replace(b"ExecStartPre=/usr/local", b"ExecStartPre=/usr/bin/true\nExecStartPre=/usr/local")
                self.loaded_drop_in.write_bytes(contents)
            else:
                self.loaded_drop_in.unlink(missing_ok=True)
            self.loaded_paths.write_text(self.disk_unit_paths())
            return 0
        raise AssertionError(args)

    def run(self, command, args):
        if command == "systemctl":
            if args[0] in ("start", "restart", "reload", "enable", "disable", "stop"):
                with (self.root / "systemd-job").open("a") as jobs:
                    fcntl.flock(jobs, fcntl.LOCK_EX)
                    return Unit().systemctl(args)
            return self.systemctl(args)
        if command == "kill":
            assert args == ["-USR2", self.master.read_text()]
            pid = self.spawn()
            self.worker.write_text(pid)
            self.mapping.write_bytes((self.root / MAP).read_bytes())
            self.save(self.processes() + [pid])  # The previous worker can keep its streams.
            return 0
        if command == "haproxy":
            assert args[:3] == ["-c", "-q", "-f"]
            assert self.root / CONFIG == Path(args[3])
            return int("render" in self.mode)
        if command == "ss":
            if args[1] == "-ltnp" and self.active:
                pids = [self.worker.read_text()]
                retired = self.root / "retired-listener"
                if "drain-listener" in self.mode and not retired.exists():
                    pids.append(self.processes()[-2])
                    retired.touch()
                for address in ("0.0.0.0", "[::]"):
                    owners = ",".join(f'("haproxy",pid={pid},fd=5)' for pid in pids)
                    print(f"LISTEN 0 128 {address}:8443 *:* users:({owners})")
            if "established" in self.mode and "established" in args:
                print("0 0 127.0.0.1:42000 127.0.0.1:20099")
            if args == ["-H", "-ltn"]:
                if self.active or "listener" in self.mode:
                    print("LISTEN 0 128 0.0.0.0:8443 0.0.0.0:*")
                if (self.root / "tunnel-process").exists():
                    print("LISTEN 0 128 127.0.0.1:20099 0.0.0.0:*")
            return 0
        if command == "tls-client-hello":
            assert args[0] in ("127.0.0.1", "::1") and args[1] == "8443"
            if (self.root / "require-lock-during-probe").exists():
                assert (self.root / LOCK).exists()
                assert all(r.state == "off" for r in POLICY["parse_routes"]((self.root / ROUTES).read_text()).values())
            if not self.active or "tls-error" in self.mode:
                return 4
            if "probe-rate" in self.mode:
                clock = self.root / "probe-clock"
                now = float(clock.read_text()) if clock.exists() else 0
                log = self.root / "probe-times"
                previous = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
                recent = [tick for address, tick in previous if address == args[0] and now - tick < 10]
                with log.open("a") as stream:
                    stream.write(json.dumps([args[0], now]) + "\n")
                if len(recent) >= 30:
                    print("probe rejected by rate limit", file=sys.stderr)
                    return 4
            names = {line.split()[0] for line in self.mapping.read_text().splitlines()}
            return int(args[-1] in names or "tls-answer" in self.mode)
        if command == "dpkg-query":
            if not self.package_present:
                return 1
            selection = "hold" if "held-package" in self.mode else "install"
            print({"-f=${db:Status-Status}": "installed", "-f=${Status}": f"{selection} ok installed"}[args[1]])
            return 0
        if command == "ufw":
            assert args == ["allow", "8443/tcp"]
            for family in ("", "6"):
                path = self.root / f"etc/ufw/user{family}.rules"
                path.parent.mkdir(parents=True, exist_ok=True)
                rule = f"-A ufw{family}-user-input -p tcp --dport 8443 -j ACCEPT\n"
                lines = path.read_text() if path.exists() else ""
                if rule not in lines:
                    path.write_text(lines + rule)
            return 0
        if command == "getent":
            database, name = args
            path, _ = POLICY["ACCOUNT_FILES"][database]
            for line in (self.root / path.lstrip("/")).read_text().splitlines():
                if line.startswith(f"{name}:"):
                    print(line)
                    return 0
            return 2
        if command == "usermod":
            assert args == ["--expiredate", "1", "tunnel-test"]
            if "missing-routes" in self.mode:
                assert (self.root / LOCK).exists() and not self.active
            else:
                assert POLICY["parse_routes"]((self.root / ROUTES).read_text())["probe"].state == "off"
            shadow = self.root / "etc/shadow"
            with tempfile.NamedTemporaryFile(mode="w", dir=shadow.parent, delete=False) as staged:
                for line in shadow.read_text().splitlines():
                    fields = line.split(":")
                    if fields[0] == "tunnel-test":
                        fields[7] = "1"
                    staged.write(":".join(fields) + "\n")
            os.replace(staged.name, shadow)
            return 0
        if command == "pkill":
            if args == ["-KILL", "-u", "901"]:
                (self.root / "tunnel-process").unlink(missing_ok=True)
            return 0
        if command == "pgrep":
            if args == ["-x", "haproxy"]:
                if "stray-process" in self.mode:
                    print("999999")
                    return 0
                if self.active:
                    print(self.master.read_text(), self.worker.read_text(), sep="\n")
                    return 0
                return 1
            exists = args[0] == "-u" and (self.root / "tunnel-process").exists()
            return 0 if exists else 1
        raise AssertionError((command, args))


CONTENDED_COMMAND = r"""
import fcntl
import os
from pathlib import Path
import runpy
import sys

flock = fcntl.flock
root = Path(os.environ["HOME_FRONT_ROOT"])

def observe_contention(file, flags):
    expected = root / "run/home-front.lock"
    if not os.path.samestat(os.fstat(file.fileno()), expected.stat()):
        raise AssertionError(f"the command locked a different file than {expected}")
    try:
        flock(file, flags | fcntl.LOCK_NB)
    except BlockingIOError:
        (root / "command-lock-blocked").touch()
        flock(file, flags)
        return
    raise AssertionError("the second command acquired the lock while the first was paused")

fcntl.flock = observe_contention
sys.argv.pop(0)
runpy.run_path(sys.argv[0], run_name="__main__")
"""


INJECT = """
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import os
import runpy
import subprocess
import sys
import time

program = sys.argv.pop(1)
cli = runpy.run_path(program)
file = cli["File"]
write, read = file.write, file.read
stat = Path.lstat
scandir = os.scandir
faults = set(os.environ.get("FRONT_FAULTS", "").split(","))
root = Path(os.environ["HOME_FRONT_ROOT"])

def injected_write(self, path):
    if ("write" in faults and path.name == "routes") or ("lock-write" in faults and path.name == "front-locked"):
        raise OSError("injected atomic write failure")
    if path.name in ("home.map", "haproxy.cfg") and f"{path.name}-write" in faults:
        raise OSError(f"injected {path.name} write failure")
    wait_for = None
    if "pause" in faults and path.name == "home.map" and not (root / "paused").exists():
        snapshot = root / "paused.tmp"
        snapshot.write_bytes(self.data)
        snapshot.replace(root / "paused")
        wait_for = root / "release"
    if "lock-race" in faults and path.name == "front-locked":
        (root / "before-lock").touch()
        wait_for = root / "paused"
    if wait_for is not None:
        deadline = time.monotonic() + 8
        while not wait_for.exists():
            if time.monotonic() > deadline:
                raise OSError("test hold timed out")
            time.sleep(0.01)
    write(self, path)

def injected_read(cls, path):
    if "lock-read" in faults and path.name == "front-locked" and path.exists():
        raise OSError("injected lock readback failure")
    record = read(path)
    if record is not None and path.name in ("home.map", "haproxy.cfg") and f"{path.name}-read" in faults:
        return cls(b"stale data", record.mode, record.owner)
    if "routes-readback" in faults and path.name == "routes" and b"probe off" in record.data:
        return cls(record.data.replace(b"probe off", b"probe on"), record.mode, record.owner)
    return record

def interrupted_sync(path):
    if path == root / "var/lib/home-front" and not (path / "front-locked").exists():
        raise KeyboardInterrupt
    sync(path)

def fail_routes_sync(path):
    if path == root / "etc/home-front":
        raise OSError("injected sync failure after routes rename")
    sync(path)

def fail_lock_sync(path):
    if path == root / "var/lib/home-front" and (path / "front-locked").exists():
        raise OSError("injected sync failure after lock rename")
    sync(path)

def fail_front_sync(path):
    if path == root / "etc/haproxy":
        raise OSError("injected HAProxy directory sync failure after rename")
    sync(path)

def injected_stat(path):
    if path.name == "front-locked":
        raise OSError("injected lock stat I/O error")
    return stat(path)

def unreadable_cgroup(path):
    if (root / "sys/fs/cgroup") in Path(path).parents:
        raise PermissionError(f"{path}: injected cgroup scan failure")
    return scandir(path)

def advance_probe_clock(seconds):
    clock = root / "probe-clock"
    now = float(clock.read_text()) if clock.exists() else 0
    clock.write_text(str(now + seconds))

file.write = injected_write
file.read = classmethod(injected_read)
if "lock-stat" in faults:
    Path.lstat = injected_stat
namespace = cli["main"].__globals__
sync = namespace["sync_directory"]
if "interrupt" in faults:
    namespace["sync_directory"] = interrupted_sync
if "routes-sync" in faults:
    namespace["sync_directory"] = fail_routes_sync
if "lock-sync" in faults:
    namespace["sync_directory"] = fail_lock_sync
if "front-sync" in faults:
    namespace["sync_directory"] = fail_front_sync
if "cgroup-unreadable" in faults:
    os.scandir = unreadable_cgroup
if "probe-rate" in faults:
    time.sleep = advance_probe_clock
    run = cli["Server"].run
    fake_runner = runpy.run_path(str(Path(program).with_name("test_front.py")))["runner"]

    def run_probe_in_process(self, *argv, allowed=(0,), timeout=30):
        if argv[0] != "tls-client-hello":
            return run(self, *argv, allowed=allowed, timeout=timeout)
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = fake_runner(argv)
        if code not in allowed:
            raise cli["Error"](stderr.getvalue().strip() or f"TLS probe exited {code}")
        return subprocess.CompletedProcess(argv, code, stdout.getvalue(), stderr.getvalue())

    cli["Server"].run = run_probe_in_process
sys.exit(cli["main"]())
"""


def runner(argv):
    command, *args = argv
    unit = Unit()
    with (unit.root / "front-calls").open("a") as log:
        log.write(json.dumps([command, *args]) + "\n")
    return unit.run(command, args)


class FrontTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="home front-"))).resolve()
        for directory in ("run", "etc/haproxy", "var/lib/home-front", "sys/fs/cgroup/system.slice"):
            (self.root / directory).mkdir(mode=0o700, parents=True)
        self.write(ROUTES, FIXTURE)
        self.write("etc/home-front/config", "zone = home.example.net\n")
        self.write("etc/passwd", PASSWD)
        self.write("etc/shadow", SHADOW)
        self.write("etc/group", GROUP)
        drop_in = DROP_IN_PATH.read_text()
        self.write(DROP_IN, drop_in)
        self.write("unit-drop-in", drop_in)
        self.write("etc/home-front/machines", "tunnel-test listen 20099,20199\n"
                   "other-test listen 20097\njump-test open 20199\n")
        script = self.write("runner", f"#!/bin/sh\nexec {shlex.quote(sys.executable)} "
                            f"{shlex.quote(str(Path(__file__).resolve()))} --runner \"$@\"\n")
        script.chmod(0o700)
        self.env = {**os.environ, "HOME_FRONT_ROOT": str(self.root), "HOME_FRONT_RUNNER": str(script)}

    def write(self, name, contents):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
        path.chmod(0o600)
        return path

    def launch(self, *args, faults="", inject=False, direct=False, contended=False):
        if direct:
            argv = [self.env["HOME_FRONT_RUNNER"], *args]
        elif contended:
            argv = [sys.executable, "-c", CONTENDED_COMMAND, PROGRAM, *args]
        elif inject:
            argv = [sys.executable, "-c", INJECT, PROGRAM, *args]
        else:
            argv = [sys.executable, PROGRAM, *args]
        process = subprocess.Popen(argv, env={**self.env, "FRONT_FAULTS": faults}, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        def clean():
            if process.poll() is None:
                process.kill()
            process.communicate()

        self.addCleanup(clean)
        return process

    def finish(self, process, expected=0, outcome=None):
        stdout, stderr = process.communicate(timeout=15)
        self.assertEqual(process.returncode, expected, stdout + stderr)
        if outcome:
            self.assertTrue(stdout.startswith(outcome), stdout + stderr)
        return stdout, stderr

    def cli(self, *args, expected=0, outcome=None, **kwargs):
        return self.finish(self.launch(*args, **kwargs), expected, outcome)

    def ctl(self, op, *args, **kwargs):
        return self.cli("systemctl", op, *args, "haproxy.service", direct=True, **kwargs)

    def calls(self):
        return [json.loads(line) for line in (self.root / "front-calls").read_text().splitlines()]

    def journal(self):
        return (self.root / "unit-journal").read_text()

    def wait_until(self, check):
        deadline = time.monotonic() + 6
        while not check():
            self.assertLess(time.monotonic(), deadline, "timed out waiting for the test fixture")
            time.sleep(0.01)

    def test_start_replaces_stale_render_and_omits_off_routes_and_names_from_logs(self):
        self.ctl("start")
        self.assertIn(HOST + " probe\n", (self.root / MAP).read_text())
        self.write(ROUTES, FIXTURE.replace("probe on", "probe off"))
        self.ctl("restart")
        self.assertEqual((self.root / MAP).read_text(), HOST2 + " probe2\n")
        self.assertEqual((self.root / "unit-map").read_text(), HOST2 + " probe2\n")
        config = (self.root / CONFIG).read_text()
        self.assertNotIn("\nbackend probe\n", config)
        self.assertNotIn("20099", config)
        self.assertIn("\nbackend probe2\n", config)
        self.assertIn('log-format "%ci %b %Tw/%Tc/%Tt %U/%B %ts"', config)
        self.assertIn("bind :8443\n    bind :::8443 v6only", config)

    def test_managed_front_has_no_admin_socket(self):
        self.assertEqual(DROP_IN_PATH.read_bytes(), POLICY["FRONT_DROP_IN_CONTENT"])
        drop_in = DROP_IN_PATH.read_text()
        starts = [line.partition("=")[2] for line in drop_in.splitlines() if line.startswith("ExecStart=")]
        self.assertEqual(len(starts), 2)
        self.assertEqual(starts[0], "")  # Reset the package's ExecStart, which uses EXTRAOPTS.
        argv = shlex.split(starts[1])
        self.assertFalse(any(arg.startswith("-S") or "haproxy-master.sock" in arg or "EXTRAOPTS" in arg
                             for arg in argv))
        self.ctl("start")
        self.assertNotRegex((self.root / CONFIG).read_text(), r"(?m)^\s*stats\s+socket\b")

    def test_route_is_created_off_and_on_reloads_the_running_front(self):
        self.ctl("start")
        for account, port, reason in (("jump-test", "20199", "cannot listen on service port"),
                                      ("tunnel-test", "20199", "cannot listen on service port"),
                                      ("tunnel-test", "20098", "cannot listen on service port"),
                                      ("unlisted", "20099", "is not provisioned")):
            _, stderr = self.cli("route", "extra", account, port, expected=1)
            self.assertIn(reason, stderr)
        output, _ = self.cli("route", "extra", "tunnel-test", "20099")
        self.assertRegex(output, r"\Ahttps://[a-z2-7]{16}\.home\.example\.net:8443\n\Z")
        self.assertNotIn("extra", (self.root / MAP).read_text())
        self.assertIn("20099 extra off", (self.root / ROUTES).read_text())
        self.cli("route", "extra", "tunnel-test", "20099", expected=1)
        self.cli("on", "extra")
        self.assertIn(output.strip()[8:-5] + " extra", (self.root / "unit-map").read_text())
        self.assertNotIn("enable", [entry[1] for entry in self.calls() if entry[0] == "systemctl"])

    def test_start_and_activation_omit_ports_and_accounts_outside_provisioned_service_policy(self):
        self.write("etc/home-front/machines", "tunnel-test listen 20098,20099,20199\n"
                   "other-test listen 20097\nmissing-test listen 20096\n")
        bad_rows = ("aaaaaaaabbbbbbbb tunnel-test 20098 changed-port on\n"
                    "ccccccccdddddddd tunnel-test 20199 ssh-port on\n"
                    "eeeeeeeeffffffff missing-test 20096 absent-account on\n")
        self.write(ROUTES, FIXTURE + bad_rows)
        self.ctl("start")
        journal = self.journal()
        self.assertEqual((self.root / MAP).read_text(), f"{HOST} probe\n{HOST2} probe2\n")
        config = (self.root / CONFIG).read_text()
        for name in ("changed-port", "ssh-port", "absent-account"):
            self.assertNotIn(f"backend {name}", config)
            self.assertIn(f"omitting route {name}", journal)
            self.cli("on", name, expected=1)
        self.assertNotIn("aaaaaaaabbbbbbbb", journal)
        _, stderr = self.cli("route", "extra", "tunnel-test", "20098", expected=1)
        self.assertIn("cannot listen on service port 20098", stderr)
        self.cli("route", "extra", "missing-test", "20096", expected=1)
        self.assertEqual((self.root / ROUTES).read_text(), FIXTURE + bad_rows)

    def test_failed_reload_leaves_a_durable_on_request_and_reports_it_unconfirmed(self):
        self.write(ROUTES, FIXTURE.replace("probe on", "probe off"))
        self.ctl("reload", expected=1)
        self.cli("on", "probe", expected=1)
        self.assertFalse((self.root / CONFIG).exists())
        self.assertIn("probe off", (self.root / ROUTES).read_text())
        self.ctl("start")
        _, stderr = self.cli("on", "probe", expected=1, faults="render")
        self.assertIn("reload is unconfirmed", stderr)
        self.assertIn("probe on", (self.root / ROUTES).read_text())
        self.assertNotIn(HOST + " ", (self.root / "unit-map").read_text())
        self.cli("on", "probe", expected=1, faults="post-reload")
        self.assertIn("probe on", (self.root / ROUTES).read_text())
        self.assertIn(HOST + " ", (self.root / "unit-map").read_text())
        self.cli("off", "probe", outcome="CLOSED (verified)\n")

    def test_on_reports_recovery_when_write_fails_after_the_routes_rename(self):
        self.write(ROUTES, FIXTURE.replace("probe on", "probe off"))
        self.ctl("start")
        _, stderr = self.cli("on", "probe", expected=1, faults="routes-sync", inject=True)
        self.assertIn("sync failure after routes rename", stderr)
        self.assertIn("Run home-front off probe", stderr)
        self.assertIn("probe on", (self.root / ROUTES).read_text())
        self.assertNotIn(["systemctl", "reload", "haproxy.service"], self.calls())

    def test_on_reports_failed_reload_when_only_the_hooks_account_lookup_fails(self):
        self.write(ROUTES, FIXTURE.replace("probe on", "probe off"))
        self.ctl("start")
        worker = self.root / "unit-worker"
        before = worker.read_text()
        files = {name: ((self.root / name).stat().st_ino, (self.root / name).read_bytes())
                 for name in (CONFIG, MAP)}
        _, stderr = self.cli("on", "probe", expected=1, faults="hook-lookup")
        self.assertIn("See the unit journal", stderr)
        self.assertNotIn("Permission denied", stderr)
        self.assertIn("Permission denied", self.journal())
        self.assertIn(str(self.root / "etc/shadow"), self.journal())
        self.assertIn("Run home-front off probe", stderr)
        self.assertIn("probe on", (self.root / ROUTES).read_text())
        self.assertEqual(worker.read_text(), before)
        self.assertEqual((self.root / "unit-map").read_text(), HOST2 + " probe2\n")
        for name, original in files.items():
            self.assertEqual(((self.root / name).stat().st_ino, (self.root / name).read_bytes()), original)

    def test_start_and_activation_reject_an_account_after_removal(self):
        self.ctl("start")
        self.cli("remove-machine", "tunnel-test", outcome="CLOSED (verified)\n")
        self.assertIn("tunnel-test:!:19000:0:99999:7::1:\n", (self.root / "etc/shadow").read_text())
        _, stderr = self.cli("on", "probe", expected=1)
        self.assertIn("tunnel-test is expired or not activated", stderr)
        self.write(ROUTES, FIXTURE)
        self.ctl("restart")
        self.assertIn("omitting route probe: probe: tunnel-test is expired or not activated", self.journal())
        self.assertEqual((self.root / "unit-map").read_text(), HOST2 + " probe2\n")
        self.assertNotIn("\nbackend probe\n", (self.root / CONFIG).read_text())

    def test_normal_off_restarts_all_workers_and_leaves_other_route(self):
        self.ctl("enable", "--now")
        self.cli("on", "probe2", faults="drain-listener")
        # Reload leaves the old worker behind, but waits for it to close its listening sockets.
        query = ["ss", "-H", "-ltnp", "sport = :8443"]
        self.assertGreaterEqual(self.calls().count(query), 2)
        pids = self.root / "sys/fs/cgroup/system.slice/haproxy.service/cgroup.procs"
        before = set(pids.read_text().split())
        self.assertGreater(len(before), 2)
        self.cli("off", "probe", outcome="CLOSED (verified)\n")
        self.assertTrue(before.isdisjoint(pids.read_text().split()))
        self.assertTrue((self.root / "unit-map").read_text() == HOST2 + " probe2\n")
        self.assertFalse((self.root / LOCK).exists())
        self.assertIn(["tls-client-hello", "::1", "8443", HOST], self.calls())
        self.cli("off", outcome="CLOSED (verified)\n")
        self.assertEqual((self.root / "unit-map").read_text(), "")

    def test_off_failure_matrix(self):
        cases = {
            "write": 2, "render": 2, "restart": 2, "old-worker": 2, "established": 2,
            "tls-answer": 2, "tls-error": 2, "restart,disable": 3, "restart,still-enabled": 3,
            "restart,kill": 2, "restart,lock-write": 3, "restart,lock-read": 3,
            "restart,stray-process": 3, "restart,listener": 3,
            "restart,lock-sync": 3, "write,lock-sync": 3, "tls-answer,stop": 3,
            "restart,stray-cgroup": 3, "stray-cgroup,cgroup-unreadable": 3,
        }
        for faults, code in cases.items():
            with self.subTest(faults=faults):
                self.ctl("stop")
                (self.root / LOCK).unlink(missing_ok=True)
                shutil.rmtree(self.root / CGROUP_DIRECTORY, ignore_errors=True)
                self.write(ROUTES, FIXTURE)
                self.ctl("enable", "--now")
                start = len(self.calls())
                self.cli("off", "probe", expected=code, outcome=LOCKED if code == 2 else UNCONFIRMED,
                         faults=faults, inject=True)
                calls = self.calls()[start:]
                shutdown = [call for call in calls if call[0] == "systemctl" and call[1] in ("stop", "disable", "kill")]
                self.assertEqual(shutdown, [
                    ["systemctl", "stop", "haproxy.service"],
                    ["systemctl", "disable", "haproxy.service"],
                    ["systemctl", "kill", "-s", "KILL", "haproxy.service"],
                ])
                if faults == "tls-answer,stop":
                    self.assertEqual((self.root / "unit-map").read_text(), "")
                if code == 2:
                    self.assertEqual((self.root / LOCK).read_text(), "all routes off\n")
                    self.assertEqual(self.ctl("is-enabled", expected=1)[0], "disabled\n")
                    self.assertEqual(self.ctl("is-active", expected=3)[0], "inactive\n")
                if code == 2 or any(fault in faults for fault in ("lock-write", "lock-read", "lock-sync")):
                    self.assertEqual((self.root / MAP).read_bytes(), b"")
                    self.assertNotIn("\nbackend ", (self.root / CONFIG).read_text())

    def test_fallback_requires_durable_empty_files_and_verified_shutdown(self):
        for faults, diagnostic in (
            ("home.map-write", "injected home.map write failure"),
            ("haproxy.cfg-write", "injected haproxy.cfg write failure"),
            ("front-sync", "HAProxy directory sync failure after rename"),
            ("home.map-read", "HAProxy files do not match"),
            ("haproxy.cfg-read", "HAProxy files do not match"),
            ("still-enabled", "HAProxy is not disabled"),
        ):
            with self.subTest(faults=faults):
                (self.root / LOCK).unlink(missing_ok=True)
                self.ctl("enable", "--now")
                originals = {name: (self.root / name).read_bytes() for name in (CONFIG, MAP)}
                output, _ = self.cli("off", "probe", expected=3, outcome=UNCONFIRMED,
                                     faults=f"write,{faults}", inject=True)
                self.assertIn(diagnostic, output)
                if faults == "still-enabled":
                    for name, contents in originals.items():
                        self.assertEqual((self.root / name).read_bytes(), contents)
                if faults == "home.map-write":
                    self.assertNotIn("\nbackend ", (self.root / CONFIG).read_text())
                if faults == "haproxy.cfg-write":
                    self.assertEqual((self.root / MAP).read_bytes(), b"")

    def test_fallback_verifies_closure_when_kill_reports_the_unit_is_unloaded(self):
        self.ctl("enable", "--now")
        output, _ = self.cli("off", "probe", expected=2, outcome=LOCKED, faults="write", inject=True)
        self.assertIn("Unit haproxy.service not loaded", output)
        self.assertEqual(self.ctl("is-enabled", expected=1)[0], "disabled\n")
        self.assertEqual(self.cli("ss", "-H", "-ltn", direct=True)[0], "")

    def test_fallback_stops_a_stock_start_during_the_empty_render_but_cannot_verify_hooks(self):
        self.ctl("start")
        stale_map = (self.root / MAP).read_bytes()
        stale_config = (self.root / CONFIG).read_bytes()
        (self.root / DROP_IN).unlink()
        self.cli("systemctl", "daemon-reload", direct=True)

        start = len(self.calls())
        off = self.launch("off", "probe", faults="pause", inject=True)
        try:
            self.wait_until((self.root / "paused").exists)
            self.ctl("is-active", expected=3)
            self.ctl("start")
            self.assertEqual((self.root / "unit-map").read_bytes(), stale_map)
            self.assertEqual((self.root / "unit-config").read_bytes(), stale_config)
        finally:
            (self.root / "release").touch()
        output, _ = self.finish(off, expected=3, outcome=UNCONFIRMED)
        self.assertIn("managed start and reload hooks are not effective", output)
        self.assertIn("shutdown after render: HAProxy is not stopped", output)
        self.assertIn("Stop flat-remote on the home machine", output)
        self.assertEqual((self.root / LOCK).read_text(), "all routes off\n")
        self.assertEqual((self.root / ROUTES).read_text().splitlines()[1:],
                         FIXTURE.replace("probe on", "probe off").splitlines())
        self.assertEqual((self.root / MAP).read_bytes(), b"")
        self.assertNotIn("\nbackend ", (self.root / CONFIG).read_text())
        ops = [call[1] for call in self.calls()[start:] if call[0] == "systemctl"]
        self.assertEqual([op for op in ops if op in ("restart", "stop", "disable", "kill")],
                         ["stop", "disable", "kill"] * 2)
        self.ctl("is-enabled", expected=1)
        self.ctl("is-active", expected=3)

        self.ctl("start")
        self.assertEqual((self.root / "unit-map").read_bytes(), b"")

    def test_off_persists_routes_before_querying_hooks_even_if_lock_write_fails(self):
        for faults, code, outcome in (("hooks-query-once", 2, LOCKED), ("hooks-query", 3, UNCONFIRMED),
                                      ("hooks-query,lock-write", 3, UNCONFIRMED)):
            with self.subTest(faults=faults):
                (self.root / LOCK).unlink(missing_ok=True)
                (self.root / "routes-at-hook-query").unlink(missing_ok=True)
                self.write(ROUTES, FIXTURE)
                self.ctl("enable", "--now")
                start = len(self.calls())
                output, _ = self.cli("off", "probe", expected=code, outcome=outcome, faults=faults, inject=True)
                self.assertIn("managed start and reload hooks are not effective", output)
                persisted = (self.root / ROUTES).read_bytes()
                self.assertEqual(POLICY["parse_routes"](persisted.decode())["probe"].state, "off")
                self.assertEqual((self.root / "routes-at-hook-query").read_bytes(), persisted)
                calls = self.calls()[start:]
                self.assertEqual(calls.count(["systemctl", "show", *EXEC_QUERY]), 2)
                self.assertNotIn(["systemctl", "restart", "haproxy.service"], calls)

    def test_foreign_drop_in_leaves_revocation_unconfirmed_after_all_safety_steps(self):
        self.ctl("enable", "--now")
        self.write(str(Path(DROP_IN).with_name("90-foreign.conf")), "[Service]\nRestart=on-failure\n")
        self.cli("systemctl", "daemon-reload", direct=True)
        start = len(self.calls())
        output, _ = self.cli("off", "probe", expected=3, outcome=UNCONFIRMED)
        self.assertIn("Check the unit and drop-in paths", output)
        self.assertIn("Stop flat-remote on the home machine", output)
        self.assertTrue((self.root / LOCK).exists())
        self.assertEqual((self.root / MAP).read_bytes(), b"")
        self.assertNotIn("\nbackend ", (self.root / CONFIG).read_text())
        calls = self.calls()[start:]
        self.assertEqual([call[1] for call in calls if call[0] == "systemctl"
                          and call[1] in ("stop", "disable", "kill", "restart")], ["stop", "disable", "kill"])
        self.assertEqual(calls.count(["systemctl", "is-active", "haproxy.service"]), 2)
        self.assertEqual(calls[-1], ["systemctl", "show", *PATH_QUERY])

    def test_off_uses_fallback_for_a_persistent_drop_in_pending_daemon_reload(self):
        self.ctl("enable", "--now")
        self.write(str(Path(DROP_IN).with_name("90-pending.conf")), "[Service]\nRestart=on-failure\n")
        output, _ = self.cli("systemctl", "show", *RELOAD_QUERY, direct=True)
        self.assertEqual(output, "NeedDaemonReload=yes\n")
        output, _ = self.cli("systemctl", "show", *PATH_QUERY, direct=True)
        self.assertIn(f"DropInPaths={POLICY['FRONT_DROP_IN']}\n", output)
        start = len(self.calls())
        output, _ = self.cli("off", "probe", expected=3, outcome=UNCONFIRMED)
        self.assertNotIn("CLOSED (verified)", output)
        self.assertTrue((self.root / LOCK).exists())
        self.assertEqual((self.root / MAP).read_bytes(), b"")
        calls = self.calls()[start:]
        self.assertEqual(calls[0], ["systemctl", "show", *RELOAD_QUERY])
        self.assertEqual([call[1] for call in calls if call[0] == "systemctl"
                          and call[1] in ("stop", "disable", "kill", "restart")], ["stop", "disable", "kill"])
        self.ctl("is-active", expected=3)

    def test_effective_hooks_match_every_command_in_the_real_multirecord_format(self):
        server = POLICY["Server"](self.root, self.env["HOME_FRONT_RUNNER"])
        with patch.dict(os.environ, self.env):
            self.write("unit-exec-show", EXEC_SHOW)
            self.assertTrue(server.hooks_effective())
            pre, start, render, reload = EXEC_SHOW.splitlines(keepends=True)
            for output in (
                pre + start + render,
                pre + render + reload,
                pre + start + render + reload + reload,
                pre + start + reload + render,
                pre + start.replace("-p /run/haproxy.pid", "-p /run/haproxy.pid -S /run/haproxy-master.sock")
                + render + reload,
                pre + start.replace("haproxy.cfg", "stale.cfg") + render + reload,
                EXEC_SHOW.replace("ignore_errors=no", "ignore_errors=yes", 1),
            ):
                with self.subTest(output=output):
                    self.write("unit-exec-show", output)
                    self.assertFalse(server.hooks_effective())

    def test_effective_hooks_require_debian_fragment_and_only_the_expected_drop_ins(self):
        managed = POLICY["FRONT_DROP_IN"]
        fragment = POLICY["FRONT_FRAGMENT"]
        acceptance = POLICY["FRONT_ACCEPTANCE_DROP_IN"]
        server = POLICY["Server"](self.root, self.env["HOME_FRONT_RUNNER"])
        self.write("unit-reload-needed", "no\n")
        for source, drop_ins, running_acceptance, expected in (
            (fragment, managed, "", True),
            (POLICY["FRONT_LOCAL_UNIT"], managed, "", False),
            (fragment, "", "", False),
            (fragment, f"{managed} /run/systemd/system/haproxy.service.d/override.conf", "", False),
            (fragment, f"{managed} {acceptance}", "", False),
            (fragment, f"{managed} {acceptance}", "1", True),
            (fragment, managed, "1", False),
            (fragment, f"{managed} {acceptance} /run/systemd/system/service.d/override.conf", "1", False),
        ):
            with self.subTest(fragment=source, drop_ins=drop_ins, acceptance=running_acceptance):
                self.write("unit-paths", f"FragmentPath={source}\nDropInPaths={drop_ins}\n")
                with patch.dict(os.environ, {**self.env, "HOME_FRONT_ACCEPTANCE": running_acceptance}):
                    self.assertEqual(server.hooks_effective(), expected)

    def test_route_changes_and_reconcile_require_on_disk_and_effective_hooks(self):
        self.ctl("start")
        drop_in = DROP_IN_PATH.read_text()
        for path, content in (
            (DROP_IN, drop_in + "# edited\n"),
            ("unit-drop-in", drop_in.replace("ExecStartPre=/usr/local", "ExecStartPre=/usr/bin/true\nExecStartPre=/usr/local")),
            ("unit-drop-in", drop_in.replace("ExecReload=/usr/local", "ExecReload=/usr/bin/true\nExecReload=/usr/local", 1)),
        ):
            with self.subTest(path=path, content=content):
                changed = self.write(path, content)
                start = len(self.calls())
                for args in (("on", "probe"), ("route", "extra", "tunnel-test", "20099"), ("reconcile",)):
                    _, stderr = self.cli(*args, expected=1)
                    self.assertIn("managed start and reload hooks are not effective", stderr)
                self.assertEqual((self.root / ROUTES).read_text(), FIXTURE)
                calls = self.calls()[start:]
                self.assertFalse(any(call[:2] in (["systemctl", "enable"], ["systemctl", "reload"],
                                                   ["systemctl", "restart"]) for call in calls))
                changed.write_text(drop_in)

    def test_missing_installed_routes_file_uses_global_closure_before_removal(self):
        self.ctl("enable", "--now")
        (self.root / ROUTES).unlink()
        self.write("tunnel-process", "")
        self.cli("remove-machine", "tunnel-test", expected=2, outcome=LOCKED, faults="missing-routes")
        self.assertFalse((self.root / "tunnel-process").exists())

    def test_locked_front_blocks_activation_and_covers_later_write_failure(self):
        self.ctl("enable", "--now")
        self.cli("off", "probe", expected=2, outcome=LOCKED, faults="write", inject=True)
        self.cli("off", "probe2", expected=2, outcome=LOCKED, faults="write,lock-write", inject=True)
        for args in (("on", "probe"), ("route", "extra", "tunnel-test", "20099")):
            _, stderr = self.cli(*args, expected=1)
            self.assertIn("front is locked", stderr)
        self.ctl("start")
        self.ctl("is-active")
        self.assertEqual((self.root / "unit-map").read_text(), "")
        self.assertNotIn("\nbackend ", (self.root / CONFIG).read_text())
        self.assertEqual((self.root / ROUTES).read_text(), FIXTURE)

    def test_fallback_stops_manual_start_that_read_routes_before_the_lock(self):
        for fault, code in (("", 2), ("lock-sync", 3), ("lock-read", 3)):
            with self.subTest(fault=fault):
                for name in (LOCK, "before-lock", "paused", "release"):
                    (self.root / name).unlink(missing_ok=True)
                self.ctl("enable")
                start = len(self.calls())
                off = self.launch("off", "probe", faults=f"write,lock-race,{fault}", inject=True)
                self.wait_until((self.root / "before-lock").exists)
                stop = ["systemctl", "stop", "haproxy.service"]
                self.assertFalse((self.root / LOCK).exists())
                self.assertNotIn(stop, self.calls()[start:])
                manual = self.launch("systemctl", "start", "haproxy.service", direct=True, faults="pause")
                try:
                    paused = self.root / "paused"
                    self.wait_until(lambda: paused.exists() and HOST + " probe" in paused.read_text())
                    self.wait_until(lambda: stop in self.calls()[start:])
                    self.assertEqual((self.root / LOCK).read_text(), "all routes off\n")
                    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                        os.kill(off.pid, signum)
                finally:
                    (self.root / "release").touch()
                self.finish(manual)
                output, _ = self.finish(off, expected=code, outcome=LOCKED if code == 2 else UNCONFIRMED)
                if fault == "lock-sync":
                    self.assertIn("sync failure after lock rename", output)
                shutdown = [call[1] for call in self.calls()[start:]
                            if call[0] == "systemctl" and call[1] in ("stop", "disable", "kill")]
                self.assertEqual(shutdown, ["stop", "disable", "kill"])
                self.ctl("is-active", expected=3)
                self.assertEqual(self.cli("ss", "-H", "-ltn", direct=True)[0], "")

    def test_render_aborts_when_it_cannot_determine_if_the_front_is_locked(self):
        _, stderr = self.cli("render", "--for-start", expected=1, faults="lock-stat", inject=True)
        self.assertIn("lock stat I/O error", stderr)
        self.assertFalse((self.root / MAP).exists())
        self.assertFalse((self.root / CONFIG).exists())

    def test_status_shows_route_state_port_and_front_lock_without_the_names(self):
        self.write("etc/home-front/machines", "")
        self.write("etc/home-front/admin-sources", "server.example.net 192.0.2.4\n")
        self.write("etc/ssh/sshd_config", POLICY["MARKER"] + "\n" + POLICY["INCLUDE"] + "\n")
        self.write("tunnel-process", "")
        self.write(LOCK, "all routes off\n")
        output, _ = self.cli("status")
        self.assertIn("Front locked", output)
        self.assertIn("probe | off | tunnel-test | 20099 listening", output)
        self.assertIn("probe2 | off | other-test | 20097 idle", output)
        self.assertNotIn(FIRST, output)
        self.assertNotIn(SECOND, output)

    def test_reconcile_keeps_lock_until_all_checks_pass_and_completes_after_interrupt(self):
        self.write(LOCK, "all routes off\n")
        self.write("require-lock-during-probe", "")
        for fault in ("write", "routes-readback", "enable", "restart", "old-worker", "tls-answer"):
            with self.subTest(fault=fault):
                self.ctl("disable", "--now")
                if fault == "old-worker":
                    self.ctl("start")
                start = len(self.calls())
                self.cli("reconcile", expected=1, faults=fault, inject=True)
                self.assertTrue((self.root / LOCK).exists())
                if fault in ("write", "routes-readback"):
                    self.assertNotIn(["systemctl", "enable", "haproxy.service"], self.calls()[start:])
        self.cli("reconcile", expected=1, faults="interrupt", inject=True)
        self.assertFalse((self.root / LOCK).exists())
        self.assertNotIn(" on\n", (self.root / ROUTES).read_text())
        (self.root / "require-lock-during-probe").unlink()
        self.cli("reconcile")
        self.ctl("is-enabled")
        self.ctl("is-active")
        self.assertEqual((self.root / "unit-map").read_text(), "")
        self.cli("on", "probe2")
        self.assertEqual((self.root / "unit-map").read_text(), HOST2 + " probe2\n")

    def test_reconcile_starts_empty_even_if_a_stale_front_is_already_active(self):
        self.ctl("enable", "--now")
        self.write(LOCK, "all routes off\n")
        self.write(MAP, "")
        self.write("require-lock-during-probe", "")
        self.cli("reconcile")
        self.assertEqual((self.root / "unit-map").read_text(), "")
        self.assertFalse((self.root / LOCK).exists())

    def test_change_commands_serialize_even_while_systemd_render_runs_without_the_flock(self):
        self.ctl("enable", "--now")
        first = self.launch("off", "probe", faults="pause")
        try:
            paused = self.root / "paused"
            self.wait_until(paused.exists)
            self.assertEqual(paused.read_text(), HOST2 + " probe2\n")
            second = self.launch("off", "probe2", contended=True)
            self.wait_until((self.root / "command-lock-blocked").exists)
            self.assertIn("probe2 on", (self.root / ROUTES).read_text())
        finally:
            (self.root / "release").touch()
        self.finish(first, outcome="CLOSED (verified)\n")
        self.finish(second, outcome="CLOSED (verified)\n")
        self.assertEqual((self.root / "unit-map").read_text(), "")

    def test_off_orders_its_restart_after_an_overlapping_stale_start_render(self):
        self.ctl("enable", "--now")
        first = self.launch("systemctl", "restart", "haproxy.service", direct=True, faults="pause")
        self.wait_until((self.root / "paused").exists)
        self.assertIn(HOST + " probe", (self.root / "paused").read_text())
        off = self.launch("off", "probe")
        requested = ["systemctl", "restart", "haproxy.service"]
        self.wait_until(lambda: self.calls().count(requested) == 2)
        self.assertIn("probe off", (self.root / ROUTES).read_text())
        (self.root / "release").touch()
        self.finish(first)
        self.finish(off, outcome="CLOSED (verified)\n")
        self.assertEqual((self.root / "unit-map").read_text(), HOST2 + " probe2\n")
        self.assertNotIn("\nbackend probe\n", (self.root / CONFIG).read_text())

    def test_command_waits_for_systemd_hook_to_write_haproxy_files(self):
        self.ctl("enable", "--now")
        originals = {name: ((self.root / name).stat().st_ino, (self.root / name).read_bytes())
                     for name in (CONFIG, MAP)}
        on = self.launch("on", "probe", faults="pause")
        self.wait_until((self.root / "paused").exists)
        for name, expected in originals.items():
            self.assertEqual(((self.root / name).stat().st_ino, (self.root / name).read_bytes()), expected)
        (self.root / "release").touch()
        self.finish(on)
        self.assertFalse(any((self.root / name).stat().st_ino == originals[name][0] for name in originals))

    def test_remove_closes_public_route_before_expiring_account_and_combines_outcomes(self):
        for faults, code, outcome in (("", 0, "CLOSED (verified)\n"), ("restart", 2, LOCKED),
                                      ("restart,disable", 3, UNCONFIRMED)):
            with self.subTest(faults=faults):
                (self.root / LOCK).unlink(missing_ok=True)
                self.write("etc/shadow", SHADOW)
                self.write(ROUTES, FIXTURE)
                self.ctl("enable", "--now")
                key = self.write("etc/ssh/home-tunnel/tunnel-test.keys", "key\n")
                self.write("tunnel-process", "")
                index = len(self.calls())
                self.cli("remove-machine", "tunnel-test", faults=faults, expected=code, outcome=outcome)
                self.assertFalse(key.exists())
                self.assertFalse((self.root / "tunnel-process").exists())
                calls = self.calls()[index:]
                self.assertLess(calls.index(["systemctl", "restart", "haproxy.service"]),
                                calls.index(["usermod", "--expiredate", "1", "tunnel-test"]))

    def test_denied_rows_are_omitted_at_start_and_fail_a_reload(self):
        denied = [
            ("tunnel-test", 20200, "outside-range"),
            ("tunnel-test", 20199, "ssh-port"),
            ("root", 20099, "root-account"),
            ("shell-test", 20099, "regular-shell"),
            ("password-test", 20099, "unlocked-password"),
            ("future-test", 20099, "future-expiry"),
            ("today-test", 20099, "current-expiry"),
            ("absent-test", 20099, "missing-passwd"),
            ("shadowless-test", 20099, "missing-shadow"),
        ]
        accounts = ["shell-test", "password-test", "future-test", "today-test", "shadowless-test"]
        self.write("etc/passwd", PASSWD + "".join(
            f"{name}:x:{910 + index}:900:home-front listen 20099:/nonexistent:"
            f"{'/bin/bash' if name == 'shell-test' else '/usr/sbin/nologin'}\n"
            for index, name in enumerate(accounts)
        ))
        today = int(time.time()) // 86400
        self.write("etc/shadow", SHADOW + (
            "shell-test:!:19000:0:99999:7:::\n"
            "password-test:*:19000:0:99999:7:::\n"
            "future-test:!:19000:0:99999:7::99999:\n"
            f"today-test:!:19000:0:99999:7::{today}:\n"
        ))
        contents = FIXTURE + "".join(
            f"{chr(ord('a') + index)}{'z' * 15} {name} {port} {service} on\n"
            for index, (name, port, service) in enumerate(denied)
        )
        self.write(ROUTES, contents)
        self.ctl("start")
        journal = self.journal()
        self.assertEqual((self.root / MAP).read_text(), f"{HOST} probe\n{HOST2} probe2\n")
        for _, _, service in denied:
            self.assertEqual(journal.count(f"omitting route {service}:"), 1)
            self.cli("on", service, expected=1)
            self.assertEqual((self.root / ROUTES).read_text(), contents)
        files = {name: ((self.root / name).stat().st_ino, (self.root / name).read_bytes())
                 for name in (CONFIG, MAP)}
        _, stderr = self.ctl("reload", expected=1)
        self.assertNotIn("Run home-front off outside-range", stderr)
        self.assertIn("Run home-front off outside-range", self.journal())
        for name, original in files.items():
            self.assertEqual(((self.root / name).stat().st_ino, (self.root / name).read_bytes()), original)
        for _, _, service in denied:
            self.cli("off", service, outcome="CLOSED (verified)\n")
        self.cli("on", "probe2")

    def test_malformed_routes_or_account_files_fail_the_whole_render(self):
        cases = [
            ("non-digit port", ROUTES, FIXTURE.replace("20099", "2009x"), 0o600),
            ("leading zero", ROUTES, FIXTURE.replace("20099", "020099"), 0o600),
            ("duplicate label", ROUTES, FIXTURE.replace(SECOND, FIRST), 0o600),
            ("invalid state", ROUTES, FIXTURE.replace("probe on", "probe maybe"), 0o600),
            ("duplicate passwd record", "etc/passwd", PASSWD + PASSWD.splitlines(keepends=True)[1], 0o600),
            ("short shadow record", "etc/shadow", SHADOW.replace("tunnel-test:!:19000:0:99999:7:::",
                                                               "tunnel-test:!:19000:0:99999:7::"), 0o600),
            ("missing shadow", "etc/shadow", None, 0o600),
            ("unreadable group", "etc/group", GROUP, 0),
        ]
        for case, name, contents, mode in cases:
            with self.subTest(case=case):
                path = self.root / name
                original = path.read_text()
                if contents is None:
                    path.unlink()
                else:
                    self.write(name, contents).chmod(mode)
                try:
                    self.cli("render", "--for-start", expected=1)
                    self.assertFalse((self.root / MAP).exists())
                    self.assertFalse((self.root / CONFIG).exists())
                finally:
                    path.unlink(missing_ok=True)
                    self.write(name, original)
        (self.root / "etc/shadow").unlink()
        self.write(ROUTES, FIXTURE.replace(" on", " off"))
        self.cli("render", "--for-start")
        self.assertEqual((self.root / MAP).read_text(), "")

    def test_on_fails_when_its_reload_meets_a_denied_row(self):
        self.write(ROUTES, FIXTURE.replace("probe on", "probe off"))
        self.ctl("start")
        worker = self.root / "unit-worker"
        before = worker.read_text()
        self.write("etc/shadow", SHADOW.replace("other-test:!:19000:0:99999:7:::", "other-test:!:19000:0:99999:7::1:"))
        self.write(ROUTES, FIXTURE.replace("probe on", "probe off") +
                   "zzzzzzzzzzzzzzzz unlisted 20099 other-on on\n")
        _, stderr = self.cli("on", "probe", expected=1)
        self.assertIn("Run home-front off probe to verify closure", stderr)
        self.assertIn("probe2: other-test is expired or not activated. Run home-front off probe2", stderr)
        self.assertIn("other-on: unlisted is not provisioned. Run home-front off other-on", stderr)
        self.assertIn("Run home-front off probe2", self.journal())
        self.assertNotIn("Run home-front off other-on", self.journal())
        self.assertEqual(worker.read_text(), before)

    def test_reconcile_requires_every_process_to_be_new(self):
        self.ctl("start")
        lock = self.write(LOCK, "all routes off\n")
        _, stderr = self.cli("reconcile", expected=1, faults="old-worker")
        self.assertIn("HAProxy cgroup did not fully restart", stderr)
        self.assertTrue(lock.exists())

    def test_reconcile_refuses_a_drop_in_added_during_enable(self):
        lock = self.write(LOCK, "all routes off\n")
        _, stderr = self.cli("reconcile", expected=1, faults="override-on-enable")
        self.assertIn("managed start and reload hooks are not effective", stderr)
        self.assertTrue(lock.exists())
        self.assertTrue(all(route.state == "off"
                            for route in POLICY["parse_routes"]((self.root / ROUTES).read_text()).values()))
        calls = [call[1:] for call in self.calls() if call[0] == "systemctl"]
        before = calls.index(["show", *PATH_QUERY])
        enable = calls.index(["enable", "haproxy.service"])
        check = calls.index(["show", *PATH_QUERY], enable)
        stop = calls.index(["stop", "haproxy.service"])
        disable = calls.index(["disable", "haproxy.service"])
        self.assertLess(before, enable)
        self.assertLess(enable, check)
        self.assertLess(check, stop)
        self.assertLess(stop, disable)
        self.assertFalse(any(call[0] in ("restart", "reload") for call in calls))

    def test_census_finds_a_process_systemd_does_not_report(self):
        self.ctl("start")
        output, _ = self.cli("off", "probe", expected=3, outcome=UNCONFIRMED, faults="write,stray-cgroup", inject=True)
        self.assertIn("an HAProxy process still exists", output)
        output, _ = self.cli("systemctl", "show", "--value", "-p", "ControlGroup", "haproxy.service", direct=True)
        self.assertEqual(output.strip(), "")
        self.assertTrue((self.root / CGROUP_DIRECTORY / "stray/cgroup.procs").read_text().strip())

        parent = (self.root / CGROUP_DIRECTORY).parent
        shutil.rmtree(parent)
        output, _ = self.cli("off", "probe", expected=3, outcome=UNCONFIRMED)
        self.assertIn(str(parent), output)

    def test_off_and_reconcile_pace_all_45_names_below_the_rate_limit(self):
        alphabet = "abcdefghijklmnopqrstuvwxyz234567"
        labels = [alphabet[index // 32] + alphabet[index % 32] + "z" * 14 for index in range(45)]
        routes = "".join(f"{label} tunnel-test 20099 fixture-{index} on\n" for index, label in enumerate(labels))
        for command in ("off", "reconcile"):
            with self.subTest(command=command):
                self.write(ROUTES, routes)
                if command == "reconcile":
                    self.write(LOCK, "all routes off\n")
                (self.root / "probe-clock").unlink(missing_ok=True)
                (self.root / "probe-times").unlink(missing_ok=True)
                start = len(self.calls()) if (self.root / "front-calls").exists() else 0
                self.cli(command, faults="probe-rate", inject=True,
                         outcome="CLOSED (verified)\n" if command == "off" else "Front enabled and active")
                self.assertFalse((self.root / LOCK).exists())
                self.assertEqual((self.root / ROUTES).read_text().splitlines()[1:],
                                 routes.replace(" on\n", " off\n").splitlines())
                calls = [call for call in self.calls()[start:] if call[0] == "tls-client-hello"]
                for address in ("127.0.0.1", "::1"):
                    self.assertEqual([call[-1] for call in calls if call[1] == address],
                                     [label + ".home.example.net" for label in labels])
                times = [json.loads(line)[1] for line in (self.root / "probe-times").read_text().splitlines()]
                self.assertEqual(len(times), 90)
                self.assertTrue(all(later - earlier >= 0.5 for earlier, later in zip(times, times[1:])), times)

    def test_status_marks_a_recorded_on_route_that_is_not_served(self):
        self.write("etc/home-front/machines", "")
        self.write("etc/home-front/admin-sources", "server.example.net 192.0.2.4\n")
        self.write("etc/ssh/sshd_config", POLICY["MARKER"] + "\n" + POLICY["INCLUDE"] + "\n")
        self.write("etc/shadow", SHADOW.replace("tunnel-test:!:19000:0:99999:7:::", "tunnel-test:!:19000:0:99999:7::1:"))
        output, _ = self.cli("status")
        self.assertIn("probe | on (not served: tunnel-test is expired or not activated)", output)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--runner"]:
        sys.exit(runner(sys.argv[2:]))
    unittest.main()
