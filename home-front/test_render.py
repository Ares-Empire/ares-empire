import base64
from contextlib import ExitStack, redirect_stdout
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


HERE = Path(__file__).resolve().parent
INSTALL = HERE.parent / "deploy/install-home-front.sh"
POLICY = runpy.run_path(str(HERE / "home-front"))
parse = POLICY["parse_machines"]
render = POLICY["render"]
Error = POLICY["Error"]

FIXTURES = """\
tunnel-test listen 20097,20099,20199
jump-test open 20199 alive=3x2
"""
ADMIN = (("server.example.net", "192.0.2.4"), ("admin.example.net", "192.0.2.5"))
ROOT_SETTINGS = """\
permitrootlogin prohibit-password
pubkeyauthentication yes
authenticationmethods any
authorizedkeysfile .ssh/authorized_keys .ssh/authorized_keys2
hostbasedauthentication no
gssapiauthentication no
kbdinteractiveauthentication no
"""

RUNNER = r'''#!/usr/bin/env python3
from pathlib import Path
import json
import os
import re
import shlex
import signal
import sys
import time

root = Path(os.environ["HOME_FRONT_ROOT"])
identity = os.environ.get("TEST_COMMAND", "")
mode = os.environ.get("TEST_MODE", "")
command, *args = sys.argv[1:]
with (root / "calls").open("a") as log:
    log.write(json.dumps([identity, command, *args]) + "\n")

if command == "systemctl":
    if args[0] == "show":
        options = "-oPermitRootLogin=no" if mode == "exec-override" else "$SSHD_OPTS"
        print("ExecStart={ path=/usr/sbin/sshd ; argv[]=/usr/sbin/sshd -D " + options
              + " ; ignore_errors=no ; pid=99 ; code=(null) ; status=0/0 }")
        if mode == "extra-environment-file":
            print("EnvironmentFiles=/etc/default/alternate (ignore_errors=no)")
        print("EnvironmentFiles=/etc/default/ssh (ignore_errors=yes)")
        if mode == "unit-environment":
            print("Environment=SSHD_OPTS= -f /etc/ssh/alternate.conf")
    else:
        assert (root / "var/lib/home-front/in-progress").is_file()
        count = root / "reloads"
        count.write_text(str(1 + (int(count.read_text()) if count.exists() else 0)))
        if mode == "rollback-reload-fails":
            sys.exit("injected reload failure")
        if mode == "interrupt-reload" and not (root / "signaled").exists():
            (root / "signaled").touch()
            os.kill(os.getppid(), signal.SIGHUP)
elif command == "sshd":
    path = Path(args[args.index("-f") + 1])
    live = path == root / "etc/ssh/sshd_config"
    if mode == "pause" and live and args[0] == "-T" and not (root / "paused").exists():
        (root / "paused").touch()
        deadline = time.monotonic() + 6
        while not (root / "continue").exists():
            if time.monotonic() > deadline:
                sys.exit("pause timed out")
            time.sleep(0.01)
    if args[0] == "-t":
        if mode == "fail-after-key" and live and not (root / "observed-key").exists():
            key = root / "etc/ssh/home-tunnel/jump-test.keys"
            (root / "observed-key").write_bytes(key.read_bytes())
            expiry = root / "expiry-jump-test"
            assert not expiry.exists() or expiry.read_text() == "1"
            sys.exit("injected failure before activation")
        sys.exit(0)

    def config_lines(path):
        for line in path.read_text().splitlines():
            if line.startswith("Include "):
                selector = shlex.split(line)[1]
                if selector.startswith("/etc/"):
                    selector = root / selector.lstrip("/")
                else:
                    selector = Path(selector)
                if selector.is_file():
                    yield from config_lines(selector)
            else:
                yield line

    spec = dict(piece.split("=") for piece in args[-1].split(","))
    name, address = spec["user"], spec["addr"]
    if name == "root":
        main = path.read_text()
        count = root / "reloads"
        changed = (mode in ("root-diff", "rollback-compare-fails") and live and count.exists()
                   and address == "192.0.2.5"
                   and ("home-front managed include" in main or
                        (mode == "rollback-compare-fails" and count.read_text() == "2")))
        print("permitrootlogin " + ("no" if changed or (mode == "root-disabled" and address == "192.0.2.5")
                                  else "prohibit-password"))
        print("pubkeyauthentication " + ("no" if mode == "keys-disabled" and address == "192.0.2.5" else "yes"))
        print("authenticationmethods " + ("password" if mode == "password-only" else "any"))
        acl = {
            "deny-root": "denyusers root\ndenyusers unrelated",
            "deny-source": "denyusers r??t@192.0.2.5/32",
            "allow-other-user": "allowusers unrelated",
            "deny-root-group": "denygroups ops-*",
            "allow-other-group": "allowgroups unrelated",
            "valid-acl": "allowusers root@192.0.2.0/24,!192.0.2.8\nallowgroups ops-*",
        }.get(mode)
        if acl:
            print(acl)
        key_files = {"unsafe-fallback": "/etc/ssh/home-tunnel/%u.keys",
                     "unsafe-token": "%h.keys"}.get(mode, ".ssh/authorized_keys .ssh/authorized_keys2")
        print("authorizedkeysfile", key_files)
        print("hostbasedauthentication no\ngssapiauthentication no\nkbdinteractiveauthentication no")
    else:
        matched = False
        for line in config_lines(path):
            if line.startswith("Match "):
                matched = line == "Match User " + name
            elif matched and line.startswith("    "):
                key, value = line.strip().split(maxsplit=1)
                if mode == "candidate-diff" and not live and address == "192.0.2.4" and key == "MaxSessions":
                    value = "10"
                print(key.lower(), value)
        print("pubkeyauthentication yes\ndisableforwarding no\nauthorizedkeyscommand none\ntrustedusercakeys none")
elif command == "id":
    assert args == ["-Gn", "root"]
    print("root ops-admin")
elif command == "getent":
    database, name = args
    if database == "group":
        print("hometunnel:x:900:")
    elif database == "passwd":
        name = {"901": "tunnel-test", "902": "jump-test"}.get(name, name)
        created = root / "jump-policy"
        if name == "jump-test" and (mode == "missing-passwd" or (mode == "new-account" and not created.exists())):
            sys.exit(2)
        shell = "/bin/bash" if mode == "account-collision" and name == "jump-test" else "/usr/sbin/nologin"
        uid = 901 if name == "tunnel-test" else 902
        policy = "home-front listen 20097 20099 20199" if name == "tunnel-test" else (
            created.read_text() if created.exists() else "home-front open 20199")
        if mode == "foreign-comment":
            policy = "unrelated service"
        if mode == "uid-changed" and (root / "uid-checked").exists():
            uid = 903
        print(f"{name}:x:{uid}:900:{policy}:/nonexistent:{shell}")
    elif database == "shadow":
        expiry = root / ("expiry-" + name)
        saved = expiry.read_text() if expiry.exists() else "1"
        print(f"{name}:!:1:::::{saved}:")
    else:
        sys.exit(2)
elif command == "ss":
    print("LISTEN 0 128 127.0.0.1:20199 0.0.0.0:*")
elif command in ("pgrep", "pkill") and "-f" in args:
    assert args[-3:-1] == ["-f", "--"]
    pattern = re.compile(args[-1].replace("[:space:]", r"\s"))
    titles = root / "sshd-titles"
    processes = titles.read_text().splitlines() if titles.exists() else []
    if command == "pgrep":
        probes = root / "title-probes"
        count = int(probes.read_text()) + 1 if probes.exists() else 1
        probes.write_text(str(count))
        if mode == "late-title" and count == 2:
            processes.append("sshd-session: jump-test [preauth]")
            titles.write_text("\n".join(processes))
        sys.exit(0 if any(pattern.search(process) for process in processes) else 1)
    survivors = [process for process in processes if not pattern.search(process)]
    titles.write_text("\n".join(survivors))
    sys.exit(0 if len(survivors) != len(processes) else 1)
elif command == "pgrep":
    if mode == "uid-changed":
        (root / "uid-checked").touch()
    sys.exit(0 if args == ["-u", "902"] and (root / "jump-process").exists() else 1)
elif command == "useradd":
    assert mode == "new-account" and args[-1] == "jump-test"
    assert (root / "var/lib/home-front/in-progress").is_file()
    assert not (root / "etc/ssh/home-tunnel/jump-test.keys").exists()
    assert "--expiredate" not in args
    (root / "jump-policy").write_text(args[args.index("--comment") + 1])
    # Like Debian's useradd --system: no aging fields, so the account starts without an expiry.
    (root / "expiry-jump-test").write_text("")
elif command == "usermod":
    option, expiry, name = args
    assert option == "--expiredate"
    if mode == "new-account" and expiry == "":
        assert not (root / "var/lib/home-front/in-progress").exists()
    (root / ("expiry-" + name)).write_text(expiry)
elif command == "pkill":
    if args == ["-KILL", "-u", "902"] and mode != "process-survives":
        expiry = root / "expiry-jump-test"
        assert not expiry.exists() or expiry.read_text() == "1"
        assert not (root / "etc/ssh/home-tunnel/jump-test.keys").exists()
        (root / "jump-process").unlink(missing_ok=True)
else:
    sys.exit("unexpected command: " + command)
'''


class RenderTests(unittest.TestCase):
    def test_exact_policy_and_key_restrictions(self):
        common = {
            "AuthenticationMethods": "publickey",
            "GatewayPorts": "no",
            "AllowStreamLocalForwarding": "no",
            "PermitTunnel": "no",
            "X11Forwarding": "no",
            "AllowAgentForwarding": "no",
            "PermitTTY": "no",
            "PermitUserRC": "no",
            "MaxSessions": "0",
            "ForceCommand": "/usr/sbin/nologin",
        }
        machines = parse(FIXTURES)
        blocks = render(machines).strip().split("\n\n")[1:]
        self.assertEqual(len(blocks), 2)
        for block, name, direction, listen, opened, interval, count in zip(
            blocks, machines, ("remote", "local"),
            ("127.0.0.1:20097 127.0.0.1:20099 127.0.0.1:20199", "none"),
            ("none", "127.0.0.1:20199"), ("5", "3"), ("3", "2"),
        ):
            heading, *lines = block.splitlines()
            self.assertEqual(heading, f"Match User {name}")
            self.assertEqual(len(lines), 16)
            self.assertEqual(dict(line.strip().split(maxsplit=1) for line in lines), {
                **common, "AuthorizedKeysFile": f"/etc/ssh/home-tunnel/{name}.keys",
                "AllowTcpForwarding": direction, "PermitListen": listen, "PermitOpen": opened,
                "ClientAliveInterval": interval, "ClientAliveCountMax": count,
            })
        key = "ssh-ed25519 AAAA…EXAMPLE"
        self.assertEqual(machines["tunnel-test"].authorized_key(key),
                         'restrict,port-forwarding,permitlisten="127.0.0.1:20097",'
                         'permitlisten="127.0.0.1:20099",permitlisten="127.0.0.1:20199",'
                         'command="/usr/sbin/nologin" ssh-ed25519 AAAA…EXAMPLE tunnel-test\n')
        self.assertEqual(machines["jump-test"].authorized_key(key),
                         'restrict,port-forwarding,permitopen="127.0.0.1:20199",'
                         'command="/usr/sbin/nologin" ssh-ed25519 AAAA…EXAMPLE jump-test\n')

    def test_invalid_machine_rows(self):
        for row in (
            "root listen 20001", "-bad listen 20001", "name* listen 20001", "a/b listen 20001",
            "User listen 20001", "a" * 33 + " listen 20001", "test both 20001",
            "test listen 22", "test listen 20000", "test listen 20100", "test listen 20200",
            "test listen 20001,20001", "test listen 20001,", "test listen ٢٠٠٠١",
            "test open 20101 alive=0x2", "test open 20101 alive=3x0",
            "test open 20101 alive=3:2", "test open 20101 alive=2147483648x1",
            "test open 20101\ntest listen 20101", "a listen 20001\nb listen 20001",
        ):
            with self.subTest(row=row), self.assertRaises(Error):
                parse(row)


class ScratchTests(unittest.TestCase):
    def setUp(self):
        # A space in the prefix also exercises quoted scratch Include paths.
        scratch = self.enterContext(tempfile.TemporaryDirectory(prefix="home front test-"))
        self.root = Path(scratch).resolve()
        (self.root / "run").mkdir()
        self.main = self.write("etc/ssh/sshd_config", POLICY["DEBIAN_INCLUDE"] + "\n# local settings\n")
        self.dropin = self.write("etc/ssh/sshd_config.d/10-local.conf", "# comment with Match\n")
        self.write("etc/home-front/admin-sources", "".join(f"{host} {ip}\n" for host, ip in ADMIN), 0o600)
        self.write("etc/home-front/machines", FIXTURES, 0o600)
        runner = self.write("runner", RUNNER, 0o700)
        self.env = {**os.environ, "HOME_FRONT_ROOT": str(self.root), "HOME_FRONT_RUNNER": str(runner),
                    "TEST_MODE": "", "TEST_COMMAND": ""}

    def write(self, relative, contents, mode=0o644):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
        path.chmod(mode)
        return path

    def run_command(self, *argv, mode=""):
        return subprocess.run(argv, env={**self.env, "TEST_MODE": mode}, capture_output=True,
                              text=True, timeout=20)

    def calls(self):
        return [json.loads(line) for line in (self.root / "calls").read_text().splitlines()]

    def cli(self, *args, mode=""):
        return self.run_command(sys.executable, HERE / "home-front", *args, mode=mode)

    def refused_install(self, diagnostic, mode=""):
        result = self.run_command(INSTALL, mode=mode)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(diagnostic, result.stderr)
        self.assertFalse((self.root / "reloads").exists())
        return result

    def key(self, value):
        synthetic = b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + bytes([value]) * 32
        return "ssh-ed25519 " + base64.b64encode(synthetic).decode()

    def test_installer_refuses_match_in_main_and_any_conf_dropin(self):
        hidden = self.write("etc/ssh/sshd_config.d/.hidden.conf", "# hidden\n")
        for path in (self.main, self.dropin, hidden):
            with self.subTest(path=path):
                original = path.read_text()
                path.write_text(original + " \tMaTcH User root\n")
                result = self.refused_install(path.name)
                self.assertIn("match directive", result.stderr.lower())
                path.write_text(original)

    def test_installer_accepts_only_the_two_expected_include_lines(self):
        for path, line in (
            (self.main, "Include sshd_config.d/*.conf"),
            (self.main, POLICY["DEBIAN_INCLUDE"]),
            (self.main, POLICY["INCLUDE"]),
            (self.dropin, POLICY["DEBIAN_INCLUDE"]),
            (self.dropin, "Include extras/[[:digit:]]*.conf"),
        ):
            with self.subTest(path=path, line=line):
                original = path.read_text()
                path.write_text(original + line + "\n")
                self.refused_install(f"{path}: unexpected Include directive" if path == self.dropin else
                                     f"{POLICY['CONFIG']}: unexpected Include directive")
                path.write_text(original)

    def test_installer_refuses_non_ascii_dropin_name(self):
        self.write("etc/ssh/sshd_config.d/é.conf", "Match User unrelated\n")
        self.refused_install("sshd_config.d: unsupported filename")

    def test_installer_refuses_quoted_or_noncanonical_keywords(self):
        for path in (self.main, self.dropin):
            original = path.read_text()
            for line in ('"Match" User unrelated', '"Include" extras.conf',
                         "'Match' User unrelated", 'In"cl"ude extras.conf'):
                with self.subTest(path=path, line=line):
                    path.write_text(original + line + "\n")
                    result = self.refused_install("quoted or noncanonical sshd keyword")
                    self.assertIn(path.name, result.stderr)
            path.write_text(original)
        self.assertFalse((self.root / "calls").exists())

    def test_install_repeats_cleanly_and_checks_all_connections(self):
        original = self.main.read_text()
        for _ in range(2):
            result = self.run_command(INSTALL)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.main.read_text(), original + POLICY["MARKER"] + "\n" + POLICY["INCLUDE"] + "\n")
        self.assertEqual((self.root / "etc/ssh/home-tunnel/match.conf").read_text(), render(parse(FIXTURES)))
        self.assertEqual((self.root / "usr/local/sbin/home-front").read_bytes(), (HERE / "home-front").read_bytes())
        snapshots = list((self.root / "var/lib/home-front/sshd-before").glob("*/*.conf"))
        self.assertEqual(len(snapshots), 4)
        self.assertTrue(all(path.read_text() == ROOT_SETTINGS for path in snapshots))
        calls = self.calls()
        self.assertEqual(sum(entry[1:3] == ["sshd", "-t"] for entry in calls), 4)
        for name in ("tunnel-test", "jump-test"):
            for address in ("192.0.2.1", "127.0.0.1", ADMIN[0][1]):
                checked = [entry for entry in calls if entry[-1].startswith(f"user={name},")
                           and entry[-1].endswith(f"addr={address}")]
                self.assertEqual(len(checked), 4)
                self.assertEqual(sum(entry[4] == str(self.main) for entry in checked), 2)

    def test_first_install_creates_a_private_empty_machines_file(self):
        machines = self.root / "etc/home-front/machines"
        machines.unlink()
        result = self.run_command(INSTALL)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(parse(machines.read_text()), {})
        self.assertEqual(machines.stat().st_mode & 0o777, 0o600)

    def test_candidate_mismatch_leaves_live_files_untouched(self):
        before = self.main.read_bytes()
        self.refused_install("maxsessions", mode="candidate-diff")
        self.assertEqual(self.main.read_bytes(), before)
        self.assertFalse((self.root / "etc/ssh/home-tunnel/match.conf").exists())

    def test_installer_refuses_to_change_an_existing_regular_account(self):
        self.refused_install("jump-test: existing account does not have the dedicated home-front identity",
                             mode="account-collision")
        self.assertNotIn(POLICY["INCLUDE"], self.main.read_text())

    def test_installer_refuses_global_key_path_that_can_bypass_the_include(self):
        for mode in ("unsafe-fallback", "unsafe-token"):
            with self.subTest(mode=mode):
                self.refused_install("global AuthorizedKeysFile", mode=mode)

    def test_refuses_service_configuration_arguments(self):
        for mode, diagnostic in (
            ("exec-override", "ExecStart has unsupported sshd arguments"),
            ("extra-environment-file", "multiple command or environment settings"),
            ("unit-environment", "SSHD_OPTS must come from /etc/default/ssh"),
        ):
            with self.subTest(mode=mode):
                self.refused_install(diagnostic, mode=mode)
        defaults = self.write("etc/default/ssh", 'SSHD_OPTS="-f /etc/ssh/alternate.conf"\n')
        self.refused_install("SSHD_OPTS has unsupported sshd arguments")
        self.assertNotIn(POLICY["INCLUDE"], self.main.read_text())
        defaults.write_text('# Normal Debian service options\nSSHD_OPTS="-e"\n')
        result = self.run_command(INSTALL)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_refuses_bad_root_baseline_for_any_admin_source(self):
        for mode in ("root-disabled", "keys-disabled"):
            with self.subTest(mode=mode):
                self.refused_install(f"root baseline cannot use public-key login from {' '.join(ADMIN[1])}", mode)
                self.assertNotIn(POLICY["INCLUDE"], self.main.read_text())

    def test_root_access_lists_and_authentication_methods(self):
        for mode, expected in (
            ("password-only", "AuthenticationMethods excludes publickey"),
            ("deny-root", "DenyUsers excludes root"),
            ("deny-source", "DenyUsers excludes root from admin.example.net 192.0.2.5"),
            ("allow-other-user", "AllowUsers excludes root"),
            ("deny-root-group", "DenyGroups excludes root"),
            ("allow-other-group", "AllowGroups excludes root"),
        ):
            with self.subTest(mode=mode):
                self.refused_install(expected, mode)
        installed = self.run_command(INSTALL, mode="valid-acl")
        self.assertEqual(installed.returncode, 0, installed.stderr)

    def test_kind_and_ports_cannot_change_even_after_removal(self):
        installed = self.run_command(INSTALL)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        key = self.write("jump.pub", self.key(1))
        key_file = self.write("etc/ssh/home-tunnel/jump-test.keys",
                              parse(FIXTURES)["jump-test"].authorized_key(self.key(0)))
        self.write("expiry-jump-test", "")
        for row in ("listen 20198", "open 20101"):
            with self.subTest(row=row):
                self.write("etc/home-front/machines", FIXTURES.replace("open 20199", row), 0o600)
                for command in (("add-machine", "jump-test", key), ("render",)):
                    result = self.cli(*command)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("kind and ports are fixed", result.stderr)
        removed = self.cli("remove-machine", "jump-test")
        self.assertEqual(removed.returncode, 0, removed.stdout)
        self.assertFalse(key_file.exists())
        for row in ("listen 20198", "open 20101"):
            with self.subTest(row=row):
                self.write("etc/home-front/machines", FIXTURES.replace("open 20199", row), 0o600)
                result = self.cli("add-machine", "jump-test", key)
                self.assertEqual(result.returncode, 1)
                self.assertIn("kind and ports are fixed", result.stderr)
        self.assertFalse(key_file.exists())
        self.assertEqual((self.root / "reloads").read_text(), "1")

    def test_live_mismatch_restores_previous_files_and_reloads(self):
        self.main.chmod(0o640)
        before = self.main.read_bytes()
        match = self.write("etc/ssh/home-tunnel/match.conf", "# former match file\n", 0o640)
        installed = self.write("usr/local/sbin/home-front", "# previous program\n", 0o700)
        result = self.run_command(INSTALL, mode="root-diff")
        self.assertEqual(result.returncode, 1)
        self.assertIn(ADMIN[1][1], result.stderr)
        self.assertIn("previous files restored and sshd reloaded", result.stderr)
        self.assertEqual(self.main.read_bytes(), before)
        self.assertEqual(self.main.stat().st_mode & 0o777, 0o640)
        self.assertEqual(match.read_text(), "# former match file\n")
        self.assertEqual(match.stat().st_mode & 0o777, 0o640)
        self.assertEqual(installed.read_text(), "# previous program\n")
        self.assertEqual(installed.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.root / "reloads").read_text(), "2")

    def test_removal_expires_before_kill_and_checks_live_uid(self):
        self.write("expiry-jump-test", "")
        key = self.write("etc/ssh/home-tunnel/jump-test.keys", "test key\n")
        self.write("jump-process", "")
        result = self.cli("remove-machine", "jump-test", mode="process-survives")
        self.assertEqual(result.returncode, 3)
        self.assertIn("UID 902 or sshd processes for jump-test could not be verified gone", result.stdout)
        self.assertFalse(key.exists())
        calls = self.calls()
        self.assertLess(calls.index(["", "usermod", "--expiredate", "1", "jump-test"]),
                        calls.index(["", "pkill", "-KILL", "-u", "902"]))
        self.assertIn(["", "pgrep", "-u", "902"], calls)
        result = self.cli("remove-machine", "jump-test")
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "CLOSED (verified)"))
        self.assertFalse(any(call[1] == "ss" for call in self.calls()))

    def test_removal_kills_existing_and_late_sshd_titles_for_exact_account(self):
        unrelated = ["sshd-session: jump-test-extra [preauth]", "sshd: jump-test_other [priv]",
                     "sshd-session: jump-test@example.net [priv]", "sshd-session: jump-test@example.net@notty",
                     "sshd-session: jump-test admin [priv]", "sshd-session: jump-test admin@notty",
                     "sshd: jump-test@notty", "sshd-session: jump-test\t[priv]",
                     "sshd-auth: jump-test-extra [net]", "sshd: jump-test", "sshd: jump-test [net] extra",
                     "other: jump-test [preauth]"]
        titles = self.write("sshd-titles", "\n".join([
            "sshd-session: jump-test [preauth]", "sshd-session: jump-test [priv]",
            "sshd-session: jump-test [net]", "sshd: jump-test [net]", "sshd-auth: jump-test [net]",
            "sshd-auth: jump-test [preauth]", *unrelated,
        ]))
        result = self.cli("remove-machine", "jump-test", mode="late-title")
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "CLOSED (verified)"))
        self.assertEqual(titles.read_text().splitlines(), unrelated)
        operations = [call[1] for call in self.calls() if "-f" in call and call[1] in ("pgrep", "pkill")]
        self.assertEqual(operations, ["pkill", "pkill", "pgrep", "pgrep", "pkill", "pgrep", "pgrep"])

    def test_removal_refuses_an_unrelated_comment_before_mutating(self):
        expiry = self.write("expiry-jump-test", "")
        key = self.write("etc/ssh/home-tunnel/jump-test.keys", "test key\n")
        result = self.cli("remove-machine", "jump-test", mode="foreign-comment")
        self.assertEqual(result.returncode, 3)
        self.assertIn("invalid home-front policy comment", result.stdout)
        self.assertEqual(expiry.read_text(), "")
        self.assertEqual(key.read_text(), "test key\n")
        self.assertFalse(any(call[1] in ("usermod", "pkill") for call in self.calls()))

    def test_removal_requires_the_original_passwd_uid_at_the_end(self):
        result = self.cli("remove-machine", "jump-test", mode="uid-changed")
        self.assertEqual(result.returncode, 3)
        self.assertIn("passwd UID changed during removal", result.stdout)

    def test_removal_without_passwd_is_unconfirmed(self):
        result = self.cli("remove-machine", "jump-test", mode="missing-passwd")
        self.assertEqual(result.returncode, 3)
        self.assertIn("passwd entry missing", result.stdout)
        self.assertFalse(any(call[1] in ("pkill", "pgrep") for call in self.calls()))

    def test_removal_with_a_public_route_stays_unconfirmed(self):
        self.write("etc/home-front/routes", "fixture jump-test 20199 probe on\n", 0o600)
        key = self.write("etc/ssh/home-tunnel/jump-test.keys", "test key\n")
        result = self.cli("remove-machine", "jump-test")
        self.assertEqual(result.returncode, 3)
        self.assertIn("public route closure requires the home-front server-front controls", result.stdout)
        self.assertFalse(key.exists())

    def test_new_account_starts_expired_with_fixed_policy_before_key_write(self):
        installed = self.run_command(INSTALL, mode="new-account")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        match = self.root / "etc/ssh/home-tunnel/match.conf"
        self.assertNotIn("Match User jump-test", match.read_text())
        key = self.write("jump.pub", self.key(1))
        result = self.cli("add-machine", "jump-test", key, mode="new-account")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / "jump-policy").read_text(), "home-front open 20199")
        self.assertIn("Match User jump-test", match.read_text())
        self.assertEqual((self.root / "expiry-jump-test").read_text(), "")

    def test_reauthorization_failure_leaves_expiry_and_old_key_in_place(self):
        installed = self.run_command(INSTALL)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        machine = parse(FIXTURES)["jump-test"]
        old_key = machine.authorized_key(self.key(0))
        installed_key = self.write("etc/ssh/home-tunnel/jump-test.keys", old_key)
        new_key = self.write("jump.pub", self.key(1))
        expiry = self.write("expiry-jump-test", "1")
        result = self.cli("add-machine", "jump-test", new_key, mode="fail-after-key")
        self.assertEqual(result.returncode, 1)
        self.assertIn("injected failure before activation", result.stderr)
        self.assertEqual((self.root / "observed-key").read_text(), machine.authorized_key(self.key(1)))
        self.assertEqual(installed_key.read_text(), old_key)
        self.assertEqual(expiry.read_text(), "1")
        self.assertNotIn(["", "usermod", "--expiredate", "", "jump-test"], self.calls())
        start = len(self.calls())
        result = self.cli("add-machine", "jump-test", new_key)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(installed_key.read_text(), machine.authorized_key(self.key(1)))
        self.assertEqual(expiry.read_text(), "")
        calls = self.calls()[start:]
        self.assertLess(calls.index(["", "systemctl", "reload", "ssh.service"]),
                        calls.index(["", "usermod", "--expiredate", "", "jump-test"]))

    def test_interruptions_before_and_after_clearing_expiry(self):
        bootstrap = """
import os, runpy, signal, sys
from pathlib import Path
window = sys.argv.pop(1)
namespace = runpy.run_path(sys.argv.pop(1))
root = Path(os.environ['HOME_FRONT_ROOT'])
state = root / 'var/lib/home-front'
marker = state / 'in-progress'
reloads = root / 'reloads'
before = reloads.read_text()
sync_directory = namespace['sync_directory']
activate = namespace['Server'].set_expiry
cleanup_synced = False
def track_cleanup(path):
    global cleanup_synced
    sync_directory(path)
    if path == state and not marker.exists() and reloads.read_text() != before:
        cleanup_synced = True
def interrupt_at_activation(server, *args):
    assert cleanup_synced and not marker.exists()
    if window == 'after':
        activate(server, *args)
    os.kill(os.getpid(), signal.SIGHUP)
namespace['main'].__globals__['sync_directory'] = track_cleanup
namespace['Server'].set_expiry = interrupt_at_activation
sys.exit(namespace['main']())
"""
        installed = self.run_command(INSTALL)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        machine = parse(FIXTURES)["jump-test"]
        replacement = self.write("jump.pub", self.key(1))
        marker = self.root / POLICY["IN_PROGRESS"].lstrip("/")
        reloads = self.root / "reloads"
        for window, expected_expiry in (("before", "1"), ("after", "")):
            with self.subTest(window=window):
                key = self.write(machine.key_file.lstrip("/"), machine.authorized_key(self.key(0)))
                expiry = self.write("expiry-jump-test", "1")
                count = int(reloads.read_text())
                result = self.run_command(sys.executable, "-c", bootstrap, window, HERE / "home-front",
                                          "add-machine", machine.name, replacement)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("interrupted", result.stderr)
                self.assertEqual(expiry.read_text(), expected_expiry)
                self.assertFalse(marker.exists())
                self.assertEqual(key.read_text(), machine.authorized_key(self.key(1)))
                self.assertEqual(int(reloads.read_text()), count + 1)

    def test_active_key_cannot_be_rotated_and_same_key_is_idempotent(self):
        installed = self.run_command(INSTALL)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        machine = parse(FIXTURES)["jump-test"]
        old = machine.authorized_key(self.key(0))
        installed_key = self.write("etc/ssh/home-tunnel/jump-test.keys", old)
        old_stat = installed_key.stat()
        expiry = self.write("expiry-jump-test", "")
        replacement = self.write("jump-new.pub", self.key(1))
        for value in ("", "99999"):
            with self.subTest(expiry=value):
                expiry.write_text(value)
                result = self.cli("add-machine", "jump-test", replacement)
                self.assertEqual(result.returncode, 1)
                self.assertIn("run remove-machine first", result.stderr)
                self.assertEqual((self.root / "reloads").read_text(), "1")
        repeated = self.write("jump.pub", self.key(0) + " another-comment\n")
        result = self.cli("add-machine", "jump-test", repeated)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(installed_key.read_text(), old)
        self.assertEqual(installed_key.stat().st_ino, old_stat.st_ino)
        self.assertEqual(installed_key.stat().st_mtime_ns, old_stat.st_mtime_ns)
        self.assertEqual(expiry.read_text(), "99999")

    def test_restore_skips_failed_rename_and_continues_past_failed_restore(self):
        bootstrap = """
import os, runpy, stat, sys
from pathlib import Path
script = sys.argv.pop(1)
namespace = runpy.run_path(script)
root = Path(os.environ['HOME_FRONT_ROOT'])
marker = root / 'var/lib/home-front/in-progress'
replace, fsync = Path.replace, os.fsync
backup = None
synced = set()
def track_fsync(fd):
    fsync(fd)
    if backup is None:
        return
    info = os.fstat(fd)
    if stat.S_ISREG(info.st_mode) and os.pread(fd, 4096, 0) == backup:
        synced.add('file')
    if os.path.samestat(info, marker.parent.stat()) and marker.read_bytes() == backup:
        synced.add('directory')
def rewrite(path, target):
    global backup
    if target == root / 'etc/ssh/sshd_config':
        backup = marker.read_bytes()
        marker.unlink()
        raise OSError('initial rename failed')
    if backup is not None and target != marker:
        assert marker.read_bytes() == backup
        assert synced == {'file', 'directory'}
    if target == root / 'usr/local/sbin/home-front' and target.read_text().startswith('#!/'):
        raise OSError('program restore failed')
    return replace(path, target)
os.fsync = track_fsync
Path.replace = rewrite
sys.exit(namespace['main']())
"""
        original = self.main.read_bytes()
        match = self.write("etc/ssh/home-tunnel/match.conf", "# old policy\n", 0o640)
        program = self.write("usr/local/sbin/home-front", "# old program\n", 0o700)
        result = self.run_command(sys.executable, "-c", bootstrap, HERE / "home-front", "_install")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Unchanged /etc/ssh/sshd_config", result.stdout)
        self.assertIn("Could not restore /usr/local/sbin/home-front", result.stderr)
        self.assertIn("Restored /etc/ssh/home-tunnel/match.conf", result.stdout)
        self.assertTrue(program.read_text().startswith("#!/"))
        self.assertEqual(self.main.read_bytes(), original)
        self.assertEqual(match.read_text(), "# old policy\n")
        self.assertEqual(match.stat().st_mode & 0o777, 0o640)
        self.assertEqual((self.root / "reloads").read_text(), "1")
        backup = next((self.root / POLICY["BACKUPS"].lstrip("/")).iterdir())
        marker = self.root / POLICY["IN_PROGRESS"].lstrip("/")
        self.assertEqual(marker.read_text().strip(), str(backup))
        self.assertIn("previous run interrupted", self.cli("status").stderr)
        self.assertEqual((backup / "etc/ssh/sshd_config").read_bytes(), original)
        subprocess.run(["bash", "-n", backup / "restore.sh"], check=True)

    def test_rollback_restores_using_already_durable_marker(self):
        bootstrap = """
import errno, os, runpy, sys
from pathlib import Path
namespace = runpy.run_path(sys.argv.pop(1))
marker = Path(os.environ['HOME_FRONT_ROOT']) / 'var/lib/home-front/in-progress'
write = namespace['File'].write
writes = 0
def fail_second_marker_write(record, path):
    global writes
    if path == marker:
        writes += 1
        if writes > 1:
            raise OSError(errno.ENOSPC, 'injected second marker write failure')
    write(record, path)
namespace['File'].write = fail_second_marker_write
code = namespace['main']()
assert writes == 1, writes
sys.exit(code)
"""
        original = self.main.read_bytes()
        match = self.write("etc/ssh/home-tunnel/match.conf", "# old policy\n")
        result = self.run_command(sys.executable, "-c", bootstrap, HERE / "home-front", "_install", mode="root-diff")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("previous files restored and sshd reloaded", result.stderr)
        self.assertNotIn("AssertionError", result.stderr)
        self.assertEqual(self.main.read_bytes(), original)
        self.assertEqual(match.read_text(), "# old policy\n")
        self.assertFalse((self.root / POLICY["PROGRAM"].lstrip("/")).exists())
        self.assertFalse((self.root / POLICY["IN_PROGRESS"].lstrip("/")).exists())
        self.assertEqual((self.root / "reloads").read_text(), "2")

    def test_marker_sync_failure_after_commit_does_not_roll_back(self):
        bootstrap = """
import os, runpy, sys
from pathlib import Path
script = sys.argv.pop(1)
namespace = runpy.run_path(script)
root = Path(os.environ['HOME_FRONT_ROOT'])
state = root / 'var/lib/home-front'
sync_directory = namespace['sync_directory']
def fail_after_unlink(path):
    if path == state and (root / 'reloads').exists() and not (state / 'in-progress').exists():
        raise OSError('injected marker directory sync failure')
    sync_directory(path)
namespace['main'].__globals__['sync_directory'] = fail_after_unlink
sys.exit(namespace['main']())
"""
        original = self.main.read_text()
        result = self.run_command(sys.executable, "-c", bootstrap, HERE / "home-front", "_install")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("SSH policy committed and verified", result.stderr)
        self.assertIn("injected marker directory sync failure", result.stderr)
        self.assertEqual((self.root / "reloads").read_text(), "1")
        self.assertEqual(self.main.read_text(), original + POLICY["MARKER"] + "\n" + POLICY["INCLUDE"] + "\n")
        self.assertEqual((self.root / "etc/ssh/home-tunnel/match.conf").read_text(), render(parse(FIXTURES)))
        self.assertTrue((self.root / "usr/local/sbin/home-front").is_file())
        self.assertNotIn("Restored", result.stdout)

    def test_failed_rollback_reload_or_comparison_keeps_marker(self):
        marker = self.root / POLICY["IN_PROGRESS"].lstrip("/")
        for mode in ("rollback-reload-fails", "rollback-compare-fails"):
            with self.subTest(mode=mode):
                result = self.run_command(INSTALL, mode=mode)
                self.assertEqual(result.returncode, 1)
                self.assertIn("SSH rollback unverified", result.stderr)
                self.assertIn(f"Backup: {marker.read_text().strip()}", result.stderr)
                self.assertIn("previous run interrupted", self.cli("render").stderr)
                marker.unlink()
                (self.root / "reloads").unlink()

    def test_manual_restore_and_clear_reject_a_different_backup_marker(self):
        result = self.run_command(INSTALL)
        self.assertEqual(result.returncode, 0, result.stderr)
        parent = self.root / POLICY["BACKUPS"].lstrip("/")
        backup = next(parent.iterdir())
        new_backup = parent / "newer"
        marker = self.write(POLICY["IN_PROGRESS"].lstrip("/"), str(new_backup) + "\n", 0o600)
        original = self.main.read_bytes()
        for name in ("flock", "sync"):
            self.write(f"bin/{name}", "#!/bin/sh\nexit 0\n", 0o700)
        env = {**self.env, "PATH": f"{self.root / 'bin'}:{os.environ['PATH']}"}
        script = backup / "restore.sh"
        for args in ([], ["--clear-marker"]):
            with self.subTest(args=args):
                result = subprocess.run(["bash", script, *args], capture_output=True, env=env, text=True, timeout=5)
                self.assertEqual(result.returncode, 1)
                self.assertIn("marker does not name this backup", result.stderr)
                self.assertEqual(marker.read_text().strip(), str(new_backup))
                self.assertEqual(self.main.read_bytes(), original)
        marker.write_text(str(backup) + "\n")
        subprocess.run(["bash", script, "--clear-marker"], env=env, check=True, timeout=5)
        self.assertFalse(marker.exists())

    def test_caught_signal_restores_and_clears_marker(self):
        before = self.main.read_bytes()
        match = self.write("etc/ssh/home-tunnel/match.conf", "# old policy\n", 0o640)
        result = self.run_command(INSTALL, mode="interrupt-reload")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("interrupted; previous files restored", result.stderr)
        self.assertEqual(self.main.read_bytes(), before)
        self.assertEqual(match.read_text(), "# old policy\n")
        self.assertFalse((self.root / POLICY["IN_PROGRESS"].lstrip("/")).exists())

    def test_stale_marker_refuses_with_exact_manual_restore_commands(self):
        backup = self.root / POLICY["BACKUPS"].lstrip("/") / "20261127T000000Z-test"
        backup.mkdir(parents=True)
        marker = self.write(POLICY["IN_PROGRESS"].lstrip("/"), str(backup) + "\n", 0o600)
        for argv in (("status",), ("render",), ("remove-machine", "jump-test")):
            result = self.cli(*argv)
            self.assertNotEqual(result.returncode, 0)
            log = result.stderr + result.stdout
            self.assertIn(f"Backup: {backup}", log)
            self.assertIn(f"sudo bash '{backup / 'restore.sh'}'", log)
            self.assertIn("sudo /usr/sbin/sshd -t && sudo systemctl reload ssh.service", log)
            self.assertIn(f"sudo bash '{backup / 'restore.sh'}' --clear-marker", log.splitlines())
        self.assertFalse((self.root / "calls").exists())

    def test_acceptance_baseline_precedes_changes_and_jump_tries_free_20199(self):
        shell = (HERE / "acceptance-ssh.sh").read_text()
        script = shell.split("<<'PY'\n", 1)[1].rsplit("\nPY\n", 1)[0]
        namespace = {"__name__": "test_acceptance"}
        exec(compile(script, "acceptance-ssh.sh", "exec"), namespace)
        events = []
        snapshots = self.root / "snapshots"
        snapshots.mkdir()
        for number, (host, ip) in enumerate(ADMIN, 1):
            (snapshots / f"{number:03d}-{host}-{ip}.conf").write_text(ROOT_SETTINGS)
        baseline = dict.fromkeys(ADMIN, ROOT_SETTINGS)

        def run(*argv):
            if argv[0] == "ssh-keygen":
                return SimpleNamespace(stdout="")
            if argv[0] == "ss":
                events.append(("listener-check", argv[-1]))
                return SimpleNamespace(stdout="")
            events.append(argv[1:])
            return SimpleNamespace(stdout=f"Saved root effective settings in {snapshots}\n")

        server = Mock(root=self.root, runner=None)
        server.path.side_effect = lambda path: self.root / path.lstrip("/")
        server.storage.return_value = self.root
        server.machines.return_value = parse(FIXTURES)
        server.sources.return_value = ADMIN
        server.lookup.return_value = None
        server.listeners.return_value = set()
        server.run.side_effect = run
        server.root_baseline.side_effect = lambda sources: events.append(("baseline", sources)) or baseline
        server.check_admin.side_effect = lambda path, saved: events.append(("compare", path, saved))

        class EndProbe(Exception):
            pass

        def fake_ssh(argv, *, stderr, **kwargs):
            if argv[argv.index("-l") + 1] == "tunnel-test":
                raise EndProbe
            events.append(("ssh", argv))
            os.write(stderr.fileno(), b"Authenticated to example\nremote port forwarding failed for listen port 20199\n")
            return SimpleNamespace(wait=lambda timeout: 255, poll=lambda: 255, stdin=None)

        args = SimpleNamespace(port=22, tunnel_key=self.root / "tunnel", jump_key=self.root / "jump",
                               known_hosts=self.root / "known_hosts")
        with patch("subprocess.Popen", side_effect=fake_ssh), redirect_stdout(io.StringIO()), ExitStack() as stack:
            with self.assertRaises(EndProbe):
                namespace["acceptance"](args, {**POLICY, "Server": lambda *_: server}, stack)
        self.assertEqual([event[0] for event in events], [
            "baseline", "add-machine", "compare", "add-machine", "compare", "render",
            "compare", "listener-check", "ssh", "listener-check",
        ])
        self.assertTrue(all(event[2] is baseline for event in events if event[0] == "compare"))
        self.assertEqual(events[-3], ("listener-check", "sport = :20199"))
        self.assertEqual(events[-1], ("listener-check", "sport = :20199"))
        argv = events[-2][1]
        self.assertEqual(argv[argv.index("-l") + 1], "jump-test")
        self.assertEqual(argv[argv.index("-R") + 1], "127.0.0.1:20199:127.0.0.1:9")

    def test_changing_commands_serialize_for_their_whole_run(self):
        installed = self.run_command(INSTALL)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        command = [sys.executable, str(HERE / "home-front")]

        def launch(identity, mode, *args):
            process = self.enterContext(subprocess.Popen(
                [*command, *args], env={**self.env, "TEST_COMMAND": identity, "TEST_MODE": mode},
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            ))
            self.addCleanup(lambda: process.kill() if process.poll() is None else None)
            return process

        first = launch("first", "pause", "render")
        deadline = time.monotonic() + 4
        while not (self.root / "paused").exists() and first.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue((self.root / "paused").exists(), "first command did not reach its first policy read")
        self.assertTrue((self.root / "run/home-front.lock").is_file())
        second = launch("second", "", "remove-machine", "jump-test")
        try:
            with self.assertRaises(subprocess.TimeoutExpired):
                second.communicate(timeout=0.35)
            self.assertFalse(any(call[0] == "second" for call in self.calls()))
        finally:
            (self.root / "continue").touch()
        for process in (first, second):
            stdout, stderr = process.communicate(timeout=12)
            self.assertEqual(process.returncode, 0, stdout + stderr)
        identities = [call[0] for call in self.calls() if call[0]]
        self.assertEqual(list(dict.fromkeys(identities)), ["first", "second"])
        self.assertNotIn("first", identities[identities.index("second"):])


if __name__ == "__main__":
    unittest.main()
