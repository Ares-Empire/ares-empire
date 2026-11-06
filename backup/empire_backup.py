#!/usr/bin/env python3
"""Nightly backup of the empire's data that cannot be rebuilt. What, where, how long, how to restore: docs/BACKUP.md.

Run as root by empire-backup.service (timer, 03:15). A manual run (`python3 backup/empire_backup.py`) makes today's copy again.

  /var/backups/empire/copies/YYYY-MM-DD/             plain copy, root only: to undo a mistake on the server
  /var/backups/empire/outbox/YYYY-MM-DD.tar.gz.age   the same, encrypted for the Mac (backup/serve.sh hands it out)

Each place keeps its 7 newest. Any failure ends the run with an error, so the unit's result shows it (Aresus check
"Backups"; the Mac's aresync alerts when the newest copy is older than 26 hours).

Tests: python3 -m unittest backup/test_backup.py
"""

from __future__ import annotations

import fcntl
import grp
import hashlib
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/var/backups/empire")
RECIPIENTS = Path("/etc/empire-backup/recipients.txt")  # the Mac's public age key (deploy/install-backup.sh)
GROUP = "empire-backup"                                 # the user the Mac logs in as; may read the outbox only
LOCK = Path("/run/empire-backup.lock")
KEEP = 7

# ── What goes into every copy ─────────────────────────────────────────────────
# (path in the copy, live path). A new service with data that cannot be rebuilt adds it here (docs/BACKUP.md).

# Postgres: (path in the copy, container, user, database). Custom format: pg_restore can restore all or single tables.
POSTGRES = [
    ("aresium/aresium.pgdump", "aresium-db-1", "aresium", "aresium"),
]

# SQLite: copied with SQLite's backup API, so each copy is consistent while the service keeps writing.
SQLITE = [
    ("accounts/data.db", "/var/lib/empire-accounts/pb_data/data.db"),
    ("accounts/auxiliary.db", "/var/lib/empire-accounts/pb_data/auxiliary.db"),
    ("arestemis/arestemis.db", "/root/Arestemis/data/arestemis.db"),
    ("aresus/aresus.db", "/root/aresus/data/aresus.db"),
    ("push/push.db", "/var/lib/empire-push/push.db"),
]

# Plain files: (path in the copy, live path, required). A missing required file fails the run, so a moved file is
# noticed the next night instead of silently missing from every backup.
FILES = [
    ("hub/state.json", "/root/ares-empire/data/state.json", True),
    ("hub/sync-meta.json", "/root/ares-empire/data/sync-meta.json", True),
    ("aresium/personal.json", "/root/aresium/config/personal.json", True),
    ("aresus/machines.json", "/root/aresus/machines.json", True),
    ("secrets/ares-empire.env", "/root/ares-empire/.env", True),
    ("secrets/push.env", "/root/ares-empire/push/.env", True),
    ("secrets/aresium.env", "/root/aresium/.env", True),
    ("secrets/arestemis.env", "/root/Arestemis/.env", True),
    ("secrets/aresus.env", "/root/aresus/.env", True),
    ("secrets/arestoteles.env", "/opt/arestoteles/.env", True),
    ("secrets/arestoteles-vault.env", "/root/Arestoteles/vault.env", True),
    ("secrets/aresync-config", "/root/aresync/config", True),
    ("server/Caddyfile", "/etc/caddy/Caddyfile", True),
    ("server/owner.json", "/root/.config/ares-empire/owner.json", True),
]

# Folders copied as they are: (path in the copy, live path). Skipped when the folder does not exist.
DIRS = [
    ("accounts/storage", "/var/lib/empire-accounts/pb_data/storage"),
    ("server/aresync-hooks", "/root/aresync/hooks"),
    ("secrets/empire-push", "/etc/empire-push"),
]

# The empire's own systemd units (the repos hold most of them, not all), into server/systemd/.
UNIT_DIR = Path("/etc/systemd/system")
UNIT_PATTERNS = ("ares*.service", "ares*.timer", "empire*.service", "empire*.timer")

DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ARCHIVE = re.compile(r"^\d{4}-\d{2}-\d{2}\.tar\.gz\.age$")


class BackupError(Exception):
    pass


def log(message: str) -> None:
    print(message, flush=True)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    done = subprocess.run(cmd, capture_output=True, **kwargs)
    if done.returncode != 0:
        err = done.stderr.decode(errors="replace").strip() if isinstance(done.stderr, bytes) else str(done.stderr)
        raise BackupError(f"{' '.join(cmd[:4])} … failed ({done.returncode}): {err[:300]}")
    return done


# ── Copying ───────────────────────────────────────────────────────────────────

def copy_postgres(dst: Path, container: str, user: str, database: str) -> dict[str, int]:
    """pg_dump into dst, check the dump can be read back, return the row count per table."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "wb") as out:
        done = subprocess.run(["docker", "exec", container, "pg_dump", "-U", user, "-d", database, "--format=custom"],
                              stdout=out, stderr=subprocess.PIPE)
    if done.returncode != 0:
        raise BackupError(f"pg_dump {database} failed: {done.stderr.decode(errors='replace')[:300]}")
    with open(dst, "rb") as dump:
        run(["docker", "exec", "-i", container, "pg_restore", "--list"], stdin=dump)
    # Counts are read right after the dump; a write in between can make them differ by a row (Aresium writes rarely).
    query = ("select table_name, (xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I.%I', "
             "table_schema, table_name), false, true, '')))[1]::text from information_schema.tables "
             "where table_schema = 'public' and table_type = 'BASE TABLE' order by 1")
    out = run(["docker", "exec", container, "psql", "-U", user, "-d", database, "-At", "-F", "\t", "-c", query])
    counts = {}
    for line in out.stdout.decode().splitlines():
        table, _, n = line.partition("\t")
        counts[table] = int(n)
    return counts


def copy_sqlite(src: Path, dst: Path) -> dict[str, int]:
    """Consistent copy of a live SQLite database; checks the copy and returns the row count per table."""
    if not src.is_file():
        raise BackupError(f"missing database {src}")
    owner = src.stat()
    dst.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    try:
        target = sqlite3.connect(dst)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()
    _keep_owner(src, owner)
    check = sqlite3.connect(dst)
    try:
        result = check.execute("pragma integrity_check").fetchone()[0]
        if result != "ok":
            raise BackupError(f"copy of {src} failed its integrity check: {result}")
        tables = [r[0] for r in check.execute(
            "select name from sqlite_master where type = 'table' and name not like 'sqlite_%' order by name")]
        return {t: check.execute('select count(*) from "' + t.replace('"', '""') + '"').fetchone()[0]
                for t in tables}
    finally:
        check.close()


def _keep_owner(db: Path, owner: os.stat_result) -> None:
    """Reading a WAL database can create its -wal/-shm files. Made by root, the service (another user) could no
    longer open them; give them back to the database's owner."""
    for suffix in ("-wal", "-shm"):
        side = Path(f"{db}{suffix}")
        try:
            st = side.stat()
        except FileNotFoundError:
            continue
        if (st.st_uid, st.st_gid) != (owner.st_uid, owner.st_gid):
            os.chown(side, owner.st_uid, owner.st_gid)


def copy_file(src: Path, dst: Path, required: bool) -> bool:
    if not src.is_file():
        if required:
            raise BackupError(f"missing file {src}")
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def copy_dir(src: Path, dst: Path) -> bool:
    if not src.is_dir():
        return False
    shutil.copytree(src, dst, symlinks=True)
    return True


def copy_units(dst: Path, unit_dir: Path | None = None) -> int:
    unit_dir = unit_dir if unit_dir is not None else UNIT_DIR
    n = 0
    for pattern in UNIT_PATTERNS:
        for unit in sorted(unit_dir.glob(pattern)):
            if unit.is_file():
                dst.mkdir(parents=True, exist_ok=True)
                shutil.copy2(unit, dst / unit.name)
                n += 1
        for dropin in sorted(unit_dir.glob(pattern + ".d")):
            for conf in sorted(dropin.glob("*.conf")):
                if copy_file(conf, dst / dropin.name / conf.name, True):
                    n += 1
    return n


# ── Manifest and archive ──────────────────────────────────────────────────────

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def payload_files(day_dir: Path) -> list[Path]:
    """Every regular file in the copy except the manifest, sorted, relative to the copy's folder."""
    manifest = Path("MANIFEST.json")
    files = []
    for path in day_dir.rglob("*"):
        rel = path.relative_to(day_dir)
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise BackupError(f"unsupported backup entry {rel}")
        if path.is_file() and rel != manifest:
            files.append(rel)
    return sorted(files)


def write_manifest(day_dir: Path, date: str, created: str, counts: dict[str, dict[str, int]]) -> dict:
    files = [{"path": rel.as_posix(), "bytes": (day_dir / rel).stat().st_size, "sha256": sha256(day_dir / rel)}
             for rel in payload_files(day_dir)]
    manifest = {"date": date, "created": created, "host": socket.gethostname(), "files": files, "counts": counts}
    (day_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def write_archive(day_dir: Path, date: str, out: Path, recipients: Path) -> None:
    """gzip tar of the copy, encrypted with age for the Mac. MANIFEST.json is the first member, so the Mac can check
    every following file while it streams."""
    def clean(info: tarfile.TarInfo) -> tarfile.TarInfo:
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        return info

    with open(out, "wb") as sink, subprocess.Popen(["age", "-R", str(recipients)], stdin=subprocess.PIPE,
                                                   stdout=sink, stderr=subprocess.PIPE) as age:
        try:
            with tarfile.open(fileobj=age.stdin, mode="w|gz") as tar:
                tar.add(day_dir / "MANIFEST.json", arcname=f"{date}/MANIFEST.json", filter=clean)
                for rel in payload_files(day_dir):
                    tar.add(day_dir / rel, arcname=f"{date}/{rel.as_posix()}", recursive=False, filter=clean)
        except BrokenPipeError:
            pass  # age stopped early; its exit code and message below say why
        finally:
            age.stdin.close()
            err = age.stderr.read().decode(errors="replace")
            code = age.wait()
    if code != 0:
        raise BackupError(f"age failed ({code}): {err.strip()[:300]}")


def prune(folder: Path, pattern: re.Pattern, keep: int) -> list[str]:
    """Delete all but the `keep` newest entries whose names match `pattern` (names sort by date). Nothing else."""
    names = []
    for path in folder.iterdir():
        if path.is_symlink() or not pattern.fullmatch(path.name):
            continue
        if not (path.is_dir() if pattern == DAY else path.is_file()):
            continue
        try:
            datetime.strptime(path.name[:10], "%Y-%m-%d")
        except ValueError:
            continue
        names.append(path.name)
    names.sort()
    removed = names[:-keep] if keep > 0 else names
    for name in removed:
        path = folder / name
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
            Path(f"{path}.sha256").unlink(missing_ok=True)
    return removed


# ── The nightly run ───────────────────────────────────────────────────────────

def make_copy(day_dir: Path) -> dict[str, dict[str, int]]:
    """Fill day_dir with everything listed above; returns the row counts per table, keyed by the database's path in
    the copy (for checking a restore)."""
    counts: dict[str, dict[str, int]] = {}
    for rel, container, user, database in POSTGRES:
        counts[rel] = copy_postgres(day_dir / rel, container, user, database)
    for rel, live in SQLITE:
        counts[rel] = copy_sqlite(Path(live), day_dir / rel)
    for rel, live, required in FILES:
        copy_file(Path(live), day_dir / rel, required)
    for rel, live in DIRS:
        copy_dir(Path(live), day_dir / rel)
    copy_units(day_dir / "server" / "systemd")
    return counts


def main() -> int:
    os.umask(0o077)
    if os.geteuid() != 0:
        print("run as root (empire-backup.service does)", file=sys.stderr)
        return 1
    lock = open(LOCK, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("another backup is running", file=sys.stderr)
        return 1
    if not RECIPIENTS.is_file() or not RECIPIENTS.read_text().strip():
        print(f"missing {RECIPIENTS} (the Mac's public key, see docs/BACKUP.md)", file=sys.stderr)
        return 1

    gid = grp.getgrnam(GROUP).gr_gid
    copies, outbox = ROOT / "copies", ROOT / "outbox"
    for folder, mode, group in ((ROOT, 0o750, gid), (copies, 0o700, 0), (outbox, 0o750, gid)):
        folder.mkdir(parents=True, exist_ok=True)
        os.chown(folder, 0, group)
        os.chmod(folder, mode)

    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    created = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    work = copies / f".{date}.partial"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    try:
        counts = make_copy(work)
        manifest = write_manifest(work, date, created, counts)
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise

    # Today's copy replaces an earlier one from the same day (a manual run).
    day_dir = copies / date
    old = copies / f".{date}.old"
    shutil.rmtree(old, ignore_errors=True)
    if day_dir.exists():
        day_dir.rename(old)
    work.rename(day_dir)
    shutil.rmtree(old, ignore_errors=True)

    name = f"{date}.tar.gz.age"
    partial = outbox / f".{name}.partial"
    try:
        write_archive(day_dir, date, partial, RECIPIENTS)
        digest = sha256(partial)
        sha_partial = outbox / f".{name}.sha256.partial"
        sha_partial.write_text(f"{digest}  {name}\n")
        for path in (partial, sha_partial):
            os.chown(path, 0, gid)
            os.chmod(path, 0o640)
        # The archive first, then its checksum: serve.sh lists a copy only when both are there.
        partial.rename(outbox / name)
        sha_partial.rename(outbox / f"{name}.sha256")
    finally:
        partial.unlink(missing_ok=True)
        (outbox / f".{name}.sha256.partial").unlink(missing_ok=True)

    removed = prune(copies, DAY, KEEP) + prune(outbox, ARCHIVE, KEEP)
    total = sum(f["bytes"] for f in manifest["files"])
    log(f"backup {date}: {len(manifest['files'])} files, {total / 1e6:.1f} MB; "
        f"encrypted {(outbox / name).stat().st_size / 1e6:.1f} MB; "
        + ", ".join(f"{db} {sum(c.values())} rows" for db, c in counts.items())
        + (f"; removed {', '.join(removed)}" if removed else ""))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BackupError as e:
        print(f"backup failed: {e}", file=sys.stderr)
        sys.exit(1)
