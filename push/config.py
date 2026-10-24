"""Settings of the push service (from the environment: push/.env on the server, see .env.example) and the few
definitions all its modules share."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

# Both listeners bind loopback only. Caddy on the same host proxies /api/push/* to the public one; the internal one
# (/send) is for the province services on this host and is never routed by Caddy.
HOST = "127.0.0.1"

# Which Empire service an account needs to register a device of each app (docs/PUSH.md → Public API).
APPS = {
    "de.ares-empire.empire": "empire",
    "de.ares-empire.aresium": "aresium",
    "de.ares-empire.arestemis": "arestemis",
    "de.ares-empire.aresus": "aresus",
}


class APIError(Exception):
    """An answer other than success, with its HTTP status (the contract's 400/401/403/503)."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def short(token: str) -> str:
    """How a device or Empire token appears in logs: never in full."""
    return token[:6] + "…"


@dataclass(frozen=True)
class Config:
    auth_url: str = "http://127.0.0.1:8090"
    db_path: str = "/var/lib/empire-push/push.db"
    public_port: int = 8095
    internal_port: int = 8096
    key_file: str = ""
    key_id: str = ""
    team_id: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> Config:
        return cls(
            auth_url=env.get("EMPIRE_AUTH_URL", cls.auth_url).rstrip("/"),
            db_path=env.get("PUSH_DB", cls.db_path),
            public_port=int(env.get("PUSH_PUBLIC_PORT", cls.public_port)),
            internal_port=int(env.get("PUSH_INTERNAL_PORT", cls.internal_port)),
            key_file=env.get("APNS_KEY_FILE", "").strip(),
            key_id=env.get("APNS_KEY_ID", "").strip(),
            team_id=env.get("APNS_TEAM_ID", "").strip(),
        )

    @property
    def missing_key_settings(self) -> list[str]:
        return [name for name, value in (("APNS_KEY_FILE", self.key_file), ("APNS_KEY_ID", self.key_id),
                                         ("APNS_TEAM_ID", self.team_id)) if not value]

    @property
    def dry_run(self) -> bool:
        """Without the full APNs key settings nothing is sent: messages only go to the outbox."""
        return bool(self.missing_key_settings)
