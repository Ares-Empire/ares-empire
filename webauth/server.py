#!/usr/bin/env python3
"""Ares Empire web server — static files for the hub, gated by a single-password login
with a stateless, HMAC-signed session cookie.

Ported from arestoteles/webauth (which itself ports the Aresium scheme): scrypt password
hashing + HMAC-SHA256 signed cookie, ZERO third-party deps — stdlib hashlib.scrypt + hmac +
http.server only. Serves the empire login (web/login.html) on the gate, the hub behind it.

Config (env, from .env — never committed):
  AUTH_PASSWORD_HASH   scrypt hash `scrypt:<salthex>:<dkhex>` (set via gen_password.py)
  AUTH_SESSION_SECRET  random secret used to sign session cookies
  WEB_ROOT             dir to serve (default: web)        PORT  (default: 8090)

Fail-safe: the gate is ACTIVE only when BOTH secrets are present. If either is unset the
server logs a loud warning and serves OPEN — so a bad deploy can't lock you out before the
secrets are in place. Behind nginx (which terminates TLS for www.ares-empire.de).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from base64 import urlsafe_b64decode, urlsafe_b64encode
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from time import time
from urllib.parse import parse_qs, urlparse

WEB_ROOT = os.environ.get("WEB_ROOT", "web")
# bind the docker-bridge gateway in prod (172.18.0.1) so only the containerized nginx can
# reach it — off every public interface; default 0.0.0.0 for local dev.
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8090"))
COOKIE_NAME = "empire_session"
SESSION_SECS = 30 * 24 * 60 * 60  # 30 days

HASH = os.environ.get("AUTH_PASSWORD_HASH", "")
SECRET = os.environ.get("AUTH_SESSION_SECRET", "").encode()

# ── Empire SSO (issuer) ──────────────────────────────────────────────────────
# When an authed visitor enters a province from the hub, the empire mints a short-lived,
# HMAC-signed token bound to that province (audience). The province verifies it with the
# SAME shared SSO_SECRET and starts its own session — so there's no second login. The
# token is signed over its base64url payload string, so the verifier never has to
# reproduce our JSON formatting (cross-language safe). Empty SSO_SECRET → plain redirect.
SSO_SECRET = os.environ.get("SSO_SECRET", "").encode()
SSO_TTL = 90  # seconds — just long enough for the redirect hop
PROVINCES = {
    "aresium": "https://aresium.de",
    "arestoteles": "https://arestoteles.de",
}

# ── Live hub data ────────────────────────────────────────────────────────────
# GET /api/empire serves this JSON (projects · ideas · chronicle), updated out-of-band by
# the `empire` CLI / git hooks — so working on a project reaches the site without code edits.
# The frontend falls back to the embedded empire-data.js seed when this isn't present.
STATE_PATH = os.environ.get(
    "EMPIRE_STATE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "state.json"))

# scrypt params (must match gen_password.py)
SCRYPT_N, SCRYPT_R, SCRYPT_P, SCRYPT_DKLEN, SCRYPT_MAXMEM = 16384, 8, 1, 32, 64 * 1024 * 1024

# Reachable without a session: the login flow and the one image the login page shows.
# Exact paths only. Prefix matching ("/brand/") let "/brand/../index.html" past the login (2026-10-22).
OPEN_PATHS = frozenset({"/login", "/logout", "/favicon.ico", "/brand/ares-bust.png"})


def auth_enabled() -> bool:
    return len(HASH) > 0 and len(SECRET) > 0


def verify_password(password: str) -> bool:
    parts = HASH.split(":")  # separator is ":" so the hash survives env_file interpolation
    if len(parts) != 3 or parts[0] != "scrypt":
        return False
    try:
        salt = bytes.fromhex(parts[1])
        expected = bytes.fromhex(parts[2])
        dk = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R,
                            p=SCRYPT_P, dklen=len(expected), maxmem=SCRYPT_MAXMEM)
    except Exception:
        return False
    return hmac.compare_digest(dk, expected)


def _sign(data: str) -> str:
    return urlsafe_b64encode(hmac.new(SECRET, data.encode(), hashlib.sha256).digest()).decode().rstrip("=")


def make_session_cookie() -> str:
    payload = urlsafe_b64encode(json.dumps({"exp": int(time()) + SESSION_SECS}).encode()).decode().rstrip("=")
    token = f"{payload}.{_sign(payload)}"
    return f"{COOKIE_NAME}={token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age={SESSION_SECS}"


def clear_cookie() -> str:
    return f"{COOKIE_NAME}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0"


def _sso_sign(payload: str) -> str:
    return urlsafe_b64encode(hmac.new(SSO_SECRET, payload.encode(), hashlib.sha256).digest()).decode().rstrip("=")


def mint_sso(aud: str) -> str:
    payload = urlsafe_b64encode(json.dumps({"aud": aud, "exp": int(time()) + SSO_TTL}).encode()).decode().rstrip("=")
    return f"{payload}.{_sso_sign(payload)}"


def sso_destination(to: str) -> str | None:
    """The province URL to send the visitor to — with a fresh SSO token when one can be minted.
    Returns None for an unknown province (so we never open-redirect to an arbitrary host)."""
    base = PROVINCES.get(to)
    if not base:
        return None
    return f"{base}/sso?token={mint_sso(to)}" if SSO_SECRET else f"{base}/"


def _b64pad(s: str) -> bytes:
    return urlsafe_b64decode(s + "=" * (-len(s) % 4))


def has_valid_session(cookie_header: str | None) -> bool:
    if not auth_enabled():
        return True  # gate disabled → open
    if not cookie_header:
        return False
    entry = next((c.strip() for c in cookie_header.split(";") if c.strip().startswith(COOKIE_NAME + "=")), None)
    if not entry:
        return False
    token = entry[len(COOKIE_NAME) + 1:]
    dot = token.rfind(".")
    if dot < 1:
        return False
    payload, sig = token[:dot], token[dot + 1:]
    if not hmac.compare_digest(sig, _sign(payload)):
        return False
    try:
        exp = json.loads(_b64pad(payload).decode()).get("exp")
        return isinstance(exp, int) and time() < exp
    except Exception:
        return False


# error slot in web/login.html — replaced with the error paragraph (or removed) per request
_ERR_SLOT = "<!-- error slot: the auth server injects a .err paragraph here on a failed attempt -->"


def login_page(error: str = "") -> bytes:
    err = f'<p class="err">{error}</p>' if error else ""
    try:
        with open(os.path.join(WEB_ROOT, "login.html"), "r", encoding="utf-8") as f:
            return f.read().replace(_ERR_SLOT, err).encode("utf-8")
    except OSError:
        # fallback minimal page if login.html is missing
        return (f"<!doctype html><meta charset=utf-8><title>Ares Empire</title>"
                f"<body style='background:#000;color:#e9c86b;font-family:sans-serif;text-align:center;padding-top:18vh'>"
                f"<h1 style='letter-spacing:.2em'>ARES EMPIRE</h1>{err}"
                f"<form method=POST action=/login><input type=password name=password placeholder='Access key' autofocus>"
                f"<button>Enter</button></form>").encode("utf-8")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_ROOT, **kwargs)

    def log_message(self, fmt, *args):  # quieter logs
        sys.stderr.write(f"{self.address_string()} - {fmt % args}\n")

    def _redirect(self, location: str, cookie: str | None = None) -> None:
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_html(self, body: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _authed(self) -> bool:
        return has_valid_session(self.headers.get("Cookie"))

    def _is_open(self, path: str) -> bool:
        return path in OPEN_PATHS

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/login":
            if self._authed():
                return self._redirect("/")
            return self._send_html(login_page())
        if path == "/logout":
            return self._redirect("/login", cookie=clear_cookie())
        if path == "/sso":
            # mint a province hand-off token — only for an authed empire visitor
            if not self._authed():
                return self._redirect("/login")
            to = (parse_qs(urlparse(self.path).query).get("to") or [""])[0]
            return self._redirect(sso_destination(to) or "/")
        if not self._authed() and not self._is_open(path):
            return self._redirect("/login")
        if path == "/api/empire":
            return self._send_state()
        return super().do_GET()

    def _send_state(self) -> None:
        try:
            with open(STATE_PATH, "rb") as f:
                body = f.read()
        except OSError:
            body = b"{}"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self):
        path = urlparse(self.path).path
        if not self._authed() and not self._is_open(path) and path not in ("/login", "/logout"):
            return self._redirect("/login")
        return super().do_HEAD()

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/login":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length).decode("utf-8", "replace") if length else ""
        password = (parse_qs(body).get("password") or [""])[0]
        if auth_enabled() and verify_password(password):
            return self._redirect("/", cookie=make_session_cookie())
        return self._send_html(login_page("Incorrect access key."), status=HTTPStatus.UNAUTHORIZED)


def main() -> None:
    if not auth_enabled():
        sys.stderr.write("!! WARNING: AUTH_PASSWORD_HASH / AUTH_SESSION_SECRET not set — serving OPEN (no login gate)\n")
    else:
        sys.stderr.write("Ares Empire web: login gate ACTIVE\n")
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    sys.stderr.write(f"Ares Empire web serving {WEB_ROOT} on {HOST}:{PORT}\n")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
