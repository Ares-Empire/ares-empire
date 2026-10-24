"""Checking an Empire token with the accounts server (PocketBase), as every service does
(docs/ACCOUNTS.md → How a service checks a login; same rules as webauth/server.py).

`auth-refresh` must answer 200 for the token; the returned record then says which services the account may use.
Answers are cached 60 s per token (keyed by a hash, never the token itself); outages are never cached.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from http.client import HTTPException

from push.config import APIError

CACHE_SECS = 60
CACHE_MAX = 1000


def may_use(record: dict, service: str) -> bool:
    """The account is approved and its `services` contain this one."""
    services = record.get("services")
    return record.get("approved") is True and isinstance(services, list) and service in services


class Accounts:
    def __init__(self, base_url: str, clock: Callable[[], float] = time.time):
        self.base_url = base_url.rstrip("/")
        self.clock = clock
        self._cache: dict[str, tuple[int, dict | None, float]] = {}
        self._lock = threading.Lock()

    def refresh(self, token: str, client_ip: str | None = None) -> tuple[int, dict]:
        """POST auth-refresh with the token; status 0 means unreachable or an unreadable answer."""
        headers = {"Content-Type": "application/json", "Authorization": token}
        if client_ip:
            headers["X-Forwarded-For"] = client_ip  # so PocketBase rate-limits per visitor, not per service
        request = urllib.request.Request(self.base_url + "/api/collections/users/auth-refresh", method="POST",
                                         headers=headers, data=b"{}")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                data = json.loads(response.read() or b"{}")
                return (response.status, data) if isinstance(data, dict) else (0, {})
        except urllib.error.HTTPError as e:
            e.close()
            return e.code, {}
        except (OSError, ValueError, HTTPException):
            return 0, {}

    def account(self, token: str, client_ip: str | None = None) -> dict:
        """The account record behind a valid token.

        Raises APIError 401 (token rejected), 403 (the accounts server refuses this account, e.g. no longer approved)
        or 503 (the accounts server could not be asked).
        """
        if not token:
            raise APIError(401, "unauthenticated")
        key = hashlib.sha256(token.encode()).hexdigest()
        now = self.clock()
        with self._lock:
            hit = self._cache.get(key)
        if hit and hit[2] > now:
            status, record = hit[0], hit[1]
        else:
            status, data = self.refresh(token, client_ip)
            if status == 200:
                record = data.get("record")
                if not isinstance(record, dict) or not isinstance(record.get("id"), str) or not record["id"]:
                    raise APIError(503, "The account server returned an unreadable answer.")
            elif status in (400, 401):
                status, record = 401, None
            elif status == 403:
                record = None
            else:
                raise APIError(503, "Login service unavailable, try again in a minute.")
            with self._lock:
                if len(self._cache) >= CACHE_MAX:
                    self._cache.clear()
                self._cache[key] = (status, record, now + CACHE_SECS)
        if status == 401:
            raise APIError(401, "unauthenticated")
        if status == 403:
            raise APIError(403, "This account is not active.")
        return record
