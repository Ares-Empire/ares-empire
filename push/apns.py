"""Apple Push Notification service (APNs): the message, the provider token (an ES256 JWT) and one HTTP/2 request
per device. Apple's reference: developer.apple.com → "Sending notification requests to APNs"."""

from __future__ import annotations

import base64
import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

HOSTS = {"production": "https://api.push.apple.com", "sandbox": "https://api.sandbox.push.apple.com"}
# Apple accepts a provider token for one hour and refuses new ones more often than every 20 minutes.
TOKEN_LIFETIME = 50 * 60
EXPIRATION = 24 * 60 * 60  # Apple keeps trying an offline device for a day.
MAX_PAYLOAD = 4096
INTERRUPTIONS = ("passive", "active", "time-sensitive")
# Apple's reasons that mean the token will never work again for this app: delete it.
STALE_REASONS = frozenset({"BadDeviceToken", "DeviceTokenNotForTopic"})


@dataclass(frozen=True)
class Message:
    app: str
    title: str = ""
    subtitle: str = ""
    body: str = ""
    url: str = ""
    thread: str = ""
    category: str = ""
    collapse_id: str = ""
    interruption: str = "active"
    sound: bool = False

    def payload(self) -> bytes:
        alert = {key: value for key, value in (("title", self.title), ("subtitle", self.subtitle),
                                                ("body", self.body)) if value}
        aps: dict = {"alert": alert, "interruption-level": self.interruption}
        if self.sound:
            aps["sound"] = "default"
        if self.thread:
            aps["thread-id"] = self.thread
        if self.category:
            aps["category"] = self.category
        data: dict = {"aps": aps}
        if self.url:
            data["url"] = self.url  # the app opens it when the notification is tapped
        return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()

    def headers(self, now: float) -> dict[str, str]:
        headers = {
            "apns-topic": self.app,
            "apns-push-type": "alert",
            "apns-priority": "5" if self.interruption == "passive" else "10",
            "apns-expiration": str(int(now) + EXPIRATION),
        }
        if self.collapse_id:
            headers["apns-collapse-id"] = self.collapse_id
        return headers


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class ProviderToken:
    """The JWT Apple wants in `authorization: bearer …`: ES256, header `kid` = key id, claims `iss` = team id and
    `iat`. Made once and reused for TOKEN_LIFETIME."""

    def __init__(self, key_pem: bytes, key_id: str, team_id: str, clock: Callable[[], float] = time.time):
        key = serialization.load_pem_private_key(key_pem, password=None)
        if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
            raise ValueError("The APNs key must be a P-256 (ES256) private key, as in Apple's .p8 file.")
        self._key = key
        self.key_id = key_id
        self.team_id = team_id
        self.clock = clock
        self._token: str | None = None
        self._issued = 0.0
        self._lock = threading.Lock()

    def get(self) -> str:
        with self._lock:
            now = self.clock()
            if self._token is None or now - self._issued >= TOKEN_LIFETIME:
                self._token, self._issued = self._make(now), now
            return self._token

    def renew(self, refused: str) -> None:
        """Apple refused this token (expired): make a new one next time, unless another thread already did."""
        with self._lock:
            if self._token == refused:
                self._token = None

    def _make(self, now: float) -> str:
        header = b64url(json.dumps({"alg": "ES256", "kid": self.key_id}, separators=(",", ":")).encode())
        claims = b64url(json.dumps({"iss": self.team_id, "iat": int(now)}, separators=(",", ":")).encode())
        signing_input = f"{header}.{claims}".encode()
        r, s = decode_dss_signature(self._key.sign(signing_input, ec.ECDSA(hashes.SHA256())))
        # JWS wants the raw 64-byte r || s, not the DER form `cryptography` returns.
        return f"{header}.{claims}.{b64url(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


class Transport(Protocol):
    def post(self, url: str, headers: dict[str, str], body: bytes) -> tuple[int, bytes]:
        """Status 0 means Apple could not be reached."""


class HttpxTransport:
    """HTTP/2 to Apple (APNs refuses HTTP/1.1). One connection pool, shared by the request threads."""

    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(http2=True, timeout=10.0)
        self._lock = threading.Lock()

    def post(self, url: str, headers: dict[str, str], body: bytes) -> tuple[int, bytes]:
        try:
            with self._lock:
                response = self._client.post(url, headers=headers, content=body)
            return response.status_code, response.content
        except httpx.HTTPError:
            return 0, b""


@dataclass(frozen=True)
class Outcome:
    status: str  # "sent", "stale" (the token is dead: delete it) or "failed" (try again with the next message)
    reason: str = ""


class Apns:
    def __init__(self, token: ProviderToken, transport: Transport, clock: Callable[[], float] = time.time):
        self.token = token
        self.transport = transport
        self.clock = clock

    def send(self, device_token: str, environment: str, message: Message, payload: bytes) -> Outcome:
        url = f"{HOSTS[environment]}/3/device/{device_token}"
        for attempt in range(2):
            jwt = self.token.get()
            headers = {**message.headers(self.clock()), "authorization": "bearer " + jwt}
            status, raw = self.transport.post(url, headers, payload)
            reason = apple_reason(raw)
            if status == 200:
                return Outcome("sent")
            if status == 410 or (status == 400 and reason in STALE_REASONS):
                return Outcome("stale", reason or "Unregistered")
            if status == 403 and reason == "ExpiredProviderToken" and attempt == 0:
                self.token.renew(jwt)
                continue
            break
        return Outcome("failed", reason or (f"HTTP {status}" if status else "unreachable"))


def apple_reason(raw: bytes) -> str:
    """Apple's error answer is {"reason": "..."}."""
    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        return ""
    reason = data.get("reason") if isinstance(data, dict) else None
    return reason if isinstance(reason, str) else ""
