"""Tests for the nightly backup. Temp folders only; Postgres (docker) is left out and tested live on the server.

Run: python3 -m unittest backup/test_backup.py   (the archive test needs `age`, else it is skipped)
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import empire_backup as bk  # noqa: E402

HAS_AGE = shutil.which("age") is not None and shutil.which("age-keygen") is not None


def make_db(path: Path, rows: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("pragma journal_mode = wal")
    db.execute("create table items (id integer primary key, name text)")
    db.executemany("insert into items (name) values (?)", [(f"item {i}",) for i in range(rows)])
    db.execute("create table empty (id integer)")
    db.commit()
    db.close()


class CopyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def test_sqlite_copy_is_consistent_and_counted(self) -> None:
        live = self.tmp / "live" / "app.db"
        make_db(live, 25)
        writer = sqlite3.connect(live)          # a service still writing (uncommitted)
        writer.execute("begin immediate")
        writer.execute("insert into items (name) values ('not committed')")
        counts = bk.copy_sqlite(live, self.tmp / "copy" / "app.db")
        writer.rollback()
        writer.close()
        self.assertEqual(counts, {"empty": 0, "items": 25})
        copy = sqlite3.connect(self.tmp / "copy" / "app.db")
        self.assertEqual(copy.execute("pragma integrity_check").fetchone()[0], "ok")
        copy.close()

    def test_sqlite_missing_fails(self) -> None:
        with self.assertRaises(bk.BackupError):
            bk.copy_sqlite(self.tmp / "nope.db", self.tmp / "copy.db")

    def test_sqlite_quoted_table_name(self) -> None:
        live = self.tmp / "quoted.db"
        with sqlite3.connect(live) as db:
            db.execute('create table "a""b" (id integer)')
        db.close()
        self.assertEqual(bk.copy_sqlite(live, self.tmp / "copy.db"), {'a"b': 0})

    def test_startup_files_are_in_inventory(self) -> None:
        self.assertIn(("server/owner.json", "/root/.config/ares-empire/owner.json", True), bk.FILES)
        self.assertIn(("secrets/empire-push", "/etc/empire-push"), bk.DIRS)

    def test_live_services_require_their_settings(self) -> None:
        self.assertIn(("secrets/arestoteles-vault.env", "/root/Arestoteles/vault.env", True), bk.FILES)
        self.assertIn(("secrets/push.env", "/root/ares-empire/push/.env", True), bk.FILES)

    def test_payload_links_fail_instead_of_disappearing(self) -> None:
        (self.tmp / "file").write_text("made up")
        (self.tmp / "link").symlink_to("file")
        with self.assertRaises(bk.BackupError):
            bk.write_manifest(self.tmp, "2026-10-26", "2026-10-26T00:00:00Z", {})

    def test_unit_overrides_and_link_targets_are_copied(self) -> None:
        units = self.tmp / "units"
        units.mkdir()
        target = self.tmp / "custom.service"
        target.write_text("[Service]\nExecStart=/bin/true\n")
        (units / "ares-custom.service").symlink_to(target)
        dropin = units / "ares-custom.service.d"
        dropin.mkdir()
        (dropin / "override.conf").write_text("[Service]\nRestart=always\n")
        bk.copy_units(self.tmp / "out", units)
        self.assertEqual((self.tmp / "out/ares-custom.service").read_text(), target.read_text())
        self.assertEqual((self.tmp / "out/ares-custom.service.d/override.conf").read_text(),
                         (dropin / "override.conf").read_text())

    def test_files_required_and_optional(self) -> None:
        src = self.tmp / "a.env"
        src.write_text("KEY=1\n")
        self.assertTrue(bk.copy_file(src, self.tmp / "out" / "a.env", True))
        self.assertFalse(bk.copy_file(self.tmp / "missing", self.tmp / "out" / "b", False))
        with self.assertRaises(bk.BackupError):
            bk.copy_file(self.tmp / "missing", self.tmp / "out" / "c", True)

    def test_units_only_empire_files_including_link_targets(self) -> None:
        units = self.tmp / "units"
        units.mkdir()
        for name in ("aresus.service", "empire-backup.timer", "ares-empire.service", "nametbd2-x.service",
                     "sshd.service", "aresync.timer"):
            (units / name).write_text("[Unit]\n")
        (units / "empire-link.service").symlink_to(units / "aresus.service")
        n = bk.copy_units(self.tmp / "out", units)
        self.assertEqual(n, 5)
        self.assertEqual(sorted(p.name for p in (self.tmp / "out").iterdir()),
                         ["ares-empire.service", "aresus.service", "aresync.timer", "empire-backup.timer",
                          "empire-link.service"])

    def test_make_copy_layout(self) -> None:
        live = self.tmp / "live"
        make_db(live / "a.db", 3)
        (live / "state.json").parent.mkdir(parents=True, exist_ok=True)
        (live / "state.json").write_text("{}")
        (live / "hooks").mkdir()
        (live / "hooks" / "ares-empire").write_text("#!/bin/bash\n")
        day = self.tmp / "day"
        day.mkdir()
        with mock.patch.multiple(bk, POSTGRES=[], SQLITE=[("one/a.db", str(live / "a.db"))],
                                 FILES=[("hub/state.json", str(live / "state.json"), True),
                                        ("secrets/x.env", str(live / "missing.env"), False)],
                                 DIRS=[("server/hooks", str(live / "hooks")), ("gone", str(live / "nothing"))],
                                 UNIT_DIR=self.tmp / "no-units"):
            counts = bk.make_copy(day)
        self.assertEqual(counts, {"one/a.db": {"empty": 0, "items": 3}})
        self.assertEqual([p.as_posix() for p in bk.payload_files(day)],
                         ["hub/state.json", "one/a.db", "server/hooks/ares-empire"])

    def test_missing_required_file_fails_the_copy(self) -> None:
        with mock.patch.multiple(bk, POSTGRES=[], SQLITE=[], DIRS=[],
                                 FILES=[("hub/state.json", str(self.tmp / "missing.json"), True)]):
            with self.assertRaises(bk.BackupError):
                bk.make_copy(self.tmp)


class ManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.day = self.tmp / "2026-10-26"
        (self.day / "hub").mkdir(parents=True)
        (self.day / "hub" / "state.json").write_text('{"chronicle": []}')
        (self.day / "secrets").mkdir()
        (self.day / "secrets" / "a.env").write_bytes(b"TOKEN=abc\n")
        (self.day / "nested").mkdir()
        (self.day / "nested" / "MANIFEST.json").write_text("not the real one")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def test_manifest_lists_every_file_but_itself(self) -> None:
        m = bk.write_manifest(self.day, "2026-10-26", "2026-10-26T02:15:00Z", {"x": {"t": 1}})
        self.assertEqual([f["path"] for f in m["files"]], ["hub/state.json", "nested/MANIFEST.json", "secrets/a.env"])
        self.assertEqual(m["files"][2]["sha256"], hashlib.sha256(b"TOKEN=abc\n").hexdigest())
        self.assertEqual(json.loads((self.day / "MANIFEST.json").read_text())["counts"], {"x": {"t": 1}})

    @unittest.skipUnless(HAS_AGE, "age not installed")
    def test_archive_round_trip_manifest_first(self) -> None:
        key = self.tmp / "key.txt"
        subprocess.run(["age-keygen", "-o", str(key)], check=True, capture_output=True)
        public = subprocess.run(["age-keygen", "-y", str(key)], check=True, capture_output=True, text=True).stdout
        recipients = self.tmp / "recipients.txt"
        recipients.write_text(public)
        manifest = bk.write_manifest(self.day, "2026-10-26", "2026-10-26T02:15:00Z", {})
        out = self.tmp / "2026-10-26.tar.gz.age"
        bk.write_archive(self.day, "2026-10-26", out, recipients)
        self.assertNotIn(b"TOKEN=abc", out.read_bytes())       # encrypted
        plain = subprocess.run(["age", "-d", "-i", str(key), str(out)], check=True, capture_output=True).stdout
        with tarfile.open(fileobj=io.BytesIO(plain), mode="r:gz") as tar:
            members = tar.getmembers()
            self.assertEqual(members[0].name, "2026-10-26/MANIFEST.json")
            self.assertEqual(json.loads(tar.extractfile(members[0]).read())["files"], manifest["files"])
            got = {m.name.removeprefix("2026-10-26/"): hashlib.sha256(tar.extractfile(m).read()).hexdigest()
                   for m in members[1:]}
            self.assertTrue(all(m.uid == 0 and m.uname == "" for m in members))
        self.assertEqual(got, {f["path"]: f["sha256"] for f in manifest["files"]})

    def test_age_failure_is_an_error(self) -> None:
        bk.write_manifest(self.day, "2026-10-26", "2026-10-26T02:15:00Z", {})
        bad = self.tmp / "recipients.txt"
        bad.write_text("not a key\n")
        if not HAS_AGE:
            self.skipTest("age not installed")
        with self.assertRaises(bk.BackupError):
            bk.write_archive(self.day, "2026-10-26", self.tmp / "out.age", bad)


class PruneTests(unittest.TestCase):
    def test_invalid_names_and_links_do_not_displace_copies(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "2026-10-01.tar.gz.age").write_text("keep")
            (folder / "2026-99-99.tar.gz.age").write_text("unrelated")
            (folder / "2026-10-02.tar.gz.age").symlink_to("2026-10-01.tar.gz.age")
            self.assertEqual(bk.prune(folder, bk.ARCHIVE, 1), [])
            self.assertTrue((folder / "2026-10-01.tar.gz.age").is_file())

    def test_keeps_newest_and_touches_nothing_else(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        try:
            for day in range(1, 11):
                name = f"2026-10-{day:02d}.tar.gz.age"
                (tmp / name).write_text("x")
                (tmp / f"{name}.sha256").write_text("y")
            (tmp / ".2026-10-11.tar.gz.age.partial").write_text("z")
            (tmp / "notes.txt").write_text("keep")
            removed = bk.prune(tmp, bk.ARCHIVE, 7)
            self.assertEqual(removed, [f"2026-10-0{d}.tar.gz.age" for d in (1, 2, 3)])
            left = sorted(p.name for p in tmp.iterdir())
            self.assertEqual(len([n for n in left if bk.ARCHIVE.match(n)]), 7)
            self.assertNotIn("2026-10-01.tar.gz.age.sha256", left)
            self.assertIn(".2026-10-11.tar.gz.age.partial", left)
            self.assertIn("notes.txt", left)
        finally:
            shutil.rmtree(tmp)

    def test_day_folders(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        try:
            for day in range(1, 10):
                (tmp / f"2026-10-{day:02d}").mkdir()
            (tmp / ".2026-10-10.partial").mkdir()
            self.assertEqual(bk.prune(tmp, bk.DAY, 7), ["2026-10-01", "2026-10-02"])
            self.assertTrue((tmp / ".2026-10-10.partial").exists())
        finally:
            shutil.rmtree(tmp)


class ServeTests(unittest.TestCase):
    def test_only_complete_named_archives_can_be_downloaded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / "serve.sh"
            source = (Path(__file__).parent / "serve.sh").read_text()
            script.write_text(source.replace("OUTBOX=/var/backups/empire/outbox", f'OUTBOX="{root}"'))
            logger = root / "logger"
            logger.write_text("#!/bin/sh\nexit 0\n")
            logger.chmod(0o700)
            name = "2026-10-26.tar.gz.age"
            (root / name).write_bytes(b"invented encrypted bytes")

            def request(command):
                return subprocess.run(["/bin/sh", str(script)], capture_output=True,
                                      env={"PATH": str(root) + ":" + os.defpath,
                                           "SSH_ORIGINAL_COMMAND": command})

            self.assertEqual(request("get " + name).returncode, 2)
            (root / (name + ".sha256")).write_text("fake checksum")
            result = request("get " + name)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, b"invented encrypted bytes")
            for command in ("", "sh", "get ../" + name, "get /" + name,
                            "get " + name + "; id", "get " + name + "\nwhoami"):
                with self.subTest(command=command):
                    result = request(command)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
