"""The push service's SQLite file: registered devices, and an outbox of the last messages (without device tokens)."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

OUTBOX_KEEP = 200
STALE_DAYS = 60

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    app TEXT NOT NULL,
    token TEXT NOT NULL,
    user TEXT NOT NULL,
    environment TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    UNIQUE (app, token)
);
CREATE INDEX IF NOT EXISTS devices_by_user ON devices (app, user);
CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    app TEXT NOT NULL,
    user_or_all TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    url TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    result TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Device:
    app: str
    token: str
    user: str
    environment: str
    language: str = "en"


def stamp(seconds: float) -> str:
    """UTC time as text that sorts like the time itself (2026-10-24T12:00:00Z)."""
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Store:
    """One connection, used by one thread at a time (the HTTP servers run a thread per request)."""

    def __init__(self, path: str, clock: Callable[[], float] = time.time):
        self.clock = clock
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._db:
            self._db.execute("PRAGMA journal_mode = WAL")
            self._db.executescript(SCHEMA)
            # Older installations have neither column. Defaults also backfill existing rows.
            for table in ("devices", "outbox"):
                columns = {row[1] for row in self._db.execute(f"PRAGMA table_info({table})")}
                if "language" not in columns:
                    self._db.execute(f"ALTER TABLE {table} ADD COLUMN language TEXT NOT NULL DEFAULT 'en'")

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # Devices

    def register(self, app: str, token: str, user: str, environment: str, language: str = "en") -> str | None:
        """Upsert by (app, token): the newest account wins. Returns the previous account when the token moved."""
        now = stamp(self.clock())
        with self._lock, self._db:
            row = self._db.execute("SELECT user FROM devices WHERE app = ? AND token = ?", (app, token)).fetchone()
            self._db.execute(
                "INSERT INTO devices (app, token, user, environment, language, created, updated) VALUES (?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT (app, token) DO UPDATE SET"
                " user = excluded.user, environment = excluded.environment, language = excluded.language,"
                " updated = excluded.updated",
                (app, token, user, environment, language, now, now))
        return row[0] if row and row[0] != user else None

    def unregister(self, app: str, token: str, user: str) -> bool:
        """Removes the device only while it belongs to this account (a later account keeps a token it took over)."""
        with self._lock, self._db:
            return self._db.execute("DELETE FROM devices WHERE app = ? AND token = ? AND user = ?",
                                    (app, token, user)).rowcount > 0

    def remove(self, app: str, token: str) -> None:
        """Apple called the token stale: it is gone, whoever registered it."""
        with self._lock, self._db:
            self._db.execute("DELETE FROM devices WHERE app = ? AND token = ?", (app, token))

    def devices(self, app: str, user: str | None = None) -> list[Device]:
        """The devices of one account for this app, or all of the app's devices when `user` is None."""
        query = "SELECT app, token, user, environment, language FROM devices WHERE app = ?"
        args: tuple = (app,)
        if user is not None:
            query += " AND user = ?"
            args += (user,)
        with self._lock:
            return [Device(*row) for row in self._db.execute(query + " ORDER BY created, token", args)]

    def device(self, app: str, token: str) -> Device | None:
        with self._lock:
            row = self._db.execute("SELECT app, token, user, environment, language FROM devices WHERE app = ? AND token = ?",
                                   (app, token)).fetchone()
        return Device(*row) if row else None

    def counts(self) -> dict[str, int]:
        with self._lock:
            return dict(self._db.execute("SELECT app, COUNT(*) FROM devices GROUP BY app ORDER BY app"))

    def prune(self, days: int = STALE_DAYS) -> int:
        """Drops devices whose app has not re-registered them for `days` days. Returns how many."""
        cutoff = stamp(self.clock() - days * 24 * 60 * 60)
        with self._lock, self._db:
            return self._db.execute("DELETE FROM devices WHERE updated < ?", (cutoff,)).rowcount

    # Outbox

    def log(self, app: str, user_or_all: str, title: str, body: str, url: str, result: dict,
            language: str = "en") -> None:
        """Keeps the selected text and outcome per device language; only the last OUTBOX_KEEP rows stay."""
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO outbox (at, app, user_or_all, title, body, url, language, result) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (stamp(self.clock()), app, user_or_all, title, body, url, language, json.dumps(result, sort_keys=True)))
            self._db.execute("DELETE FROM outbox WHERE id NOT IN (SELECT id FROM outbox ORDER BY id DESC LIMIT ?)",
                             (OUTBOX_KEEP,))

    def outbox(self, limit: int = OUTBOX_KEEP) -> list[dict]:
        """Newest first."""
        with self._lock:
            rows = self._db.execute("SELECT id, at, app, user_or_all, title, body, url, language, result FROM outbox"
                                    " ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        keys = ("id", "at", "app", "user_or_all", "title", "body", "url", "language", "result")
        return [{**dict(zip(keys, row)), "result": json.loads(row[-1])} for row in rows]
