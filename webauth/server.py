#!/usr/bin/env python3
"""Ares Empire web server — static files for the hub, behind a login with Empire accounts.

Accounts live in PocketBase (https://auth.ares-empire.de, see docs/ACCOUNTS.md). This server
talks to it on localhost: log in, sign up, password reset. The session cookie holds the
Empire token; every request re-checks it (approved, has the "empire" service) with a short
cache, so un-approving someone locks them out within a minute. Stdlib only.

Config (env, from .env — never committed):
  EMPIRE_AUTH_URL   PocketBase base URL (default http://127.0.0.1:8090)
  WEB_ROOT          dir to serve (default: web)        HOST / PORT
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import sys
import threading
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from time import time
from urllib.parse import parse_qs, urlparse

WEB_ROOT = os.environ.get("WEB_ROOT", "web")
# prod binds the docker-bridge gateway (172.18.0.1), off every public interface; Caddy proxies in.
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8090"))

AUTH_URL = os.environ.get("EMPIRE_AUTH_URL", "http://127.0.0.1:8090").rstrip("/")
SERVICE = "empire"
COOKIE_NAME = "empire_session"
SESSION_SECS = 30 * 24 * 60 * 60  # matches the users token duration in PocketBase
CHECK_CACHE_SECS = 60
MAX_FORM_BYTES = 10_000

# Provinces the hub can hand a logged-in visitor to. "handoff" provinces accept the Empire
# token by POST at /sso (no second login); others just get a link.
PROVINCES = {
    "aresium": {"url": "https://aresium.de", "handoff": True},
    "arestoteles": {"url": "https://arestoteles.de", "handoff": False},
}

# ── Live hub data ────────────────────────────────────────────────────────────
# GET /api/empire serves this JSON (projects · ideas · chronicle), updated out-of-band by
# empire_sync. The frontend falls back to the embedded empire-data.js seed when it's missing.
STATE_PATH = os.environ.get(
    "EMPIRE_STATE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "state.json"))

# Reachable without a session: the login pages and the images they show.
# Exact paths only. Prefix matching ("/brand/") let "/brand/../index.html" past the login (2026-10-22).
OPEN_PATHS = frozenset({"/login", "/login/email", "/signup", "/forgot", "/logout", "/favicon.ico",
                        "/brand/ares-bust-login.webp", "/brand/ares-bust-icon.png"})


# ── Talking to the accounts server ───────────────────────────────────────────

def pb_call(path: str, body: dict | None = None, token: str | None = None,
            client_ip: str | None = None) -> tuple[int, dict]:
    """POST to PocketBase. Returns (status, json); status 0 means it could not be reached."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    if client_ip:
        headers["X-Forwarded-For"] = client_ip  # so PocketBase rate-limits per visitor, not per hub
    req = urllib.request.Request(AUTH_URL + path, method="POST", headers=headers,
                                 data=json.dumps(body or {}).encode())
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except (OSError, ValueError):
        return 0, {}


def has_access(record: dict | None) -> bool:
    return bool(record) and record.get("approved") is True and SERVICE in (record.get("services") or [])


_cache: dict[str, tuple[bool, float]] = {}
_cache_lock = threading.Lock()


def token_ok(token: str) -> bool:
    """True if `token` belongs to an approved account with Empire access (cached briefly)."""
    if not token:
        return False
    key = hashlib.sha256(token.encode()).hexdigest()
    now = time()
    with _cache_lock:
        hit = _cache.get(key)
    if hit and hit[1] > now:
        return hit[0]
    status, data = pb_call("/api/collections/users/auth-refresh", token=token)
    if status == 0 or status == 429 or status >= 500:
        return False  # accounts server trouble: deny now, but don't remember it
    ok = status == 200 and has_access(data.get("record"))
    with _cache_lock:
        if len(_cache) >= 1000:
            _cache.clear()
        _cache[key] = (ok, now + CHECK_CACHE_SECS)
    return ok


def session_token(cookie_header: str | None) -> str:
    for part in (cookie_header or "").split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE_NAME:
            return value
    return ""


def session_cookie(token: str) -> str:
    return f"{COOKIE_NAME}={token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age={SESSION_SECS}"


def clear_cookie() -> str:
    return f"{COOKIE_NAME}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0"


def login(email: str, password: str, client_ip: str) -> tuple[str | None, str]:
    """Returns (token, "") on success, else (None, message for the visitor)."""
    status, data = pb_call("/api/collections/users/auth-with-password",
                           {"identity": email, "password": password}, client_ip=client_ip)
    if status == 200:
        if has_access(data.get("record")):
            return data.get("token"), ""
        return None, "This account has no access to Ares Empire."
    if status == 400:
        return None, "Wrong email or password."
    if status == 403:  # right password, but not verified and/or not approved yet
        return None, "This account isn't active yet. Confirm your email, then wait for approval."
    if status == 429:
        return None, "Too many attempts. Wait a minute and try again."
    return None, "Login is unavailable right now. Try again in a minute."


def signup(email: str, password: str, confirm: str, client_ip: str) -> str:
    """Creates the account and sends the confirmation email. Returns "" or an error message."""
    if password != confirm:
        return "The passwords don't match."
    if len(password) < 8:
        return "The password needs at least 8 characters."
    status, data = pb_call("/api/collections/users/records",
                           {"email": email, "password": password, "passwordConfirm": confirm},
                           client_ip=client_ip)
    if status == 200:
        pb_call("/api/collections/users/request-verification", {"email": email}, client_ip=client_ip)
        return ""
    fields = data.get("data") or {}
    if (fields.get("email") or {}).get("code") == "validation_not_unique":
        return "An account with this email already exists. Log in or reset your password."
    for field, label in (("email", "Email"), ("password", "Password"), ("passwordConfirm", "Password")):
        if (fields.get(field) or {}).get("message"):
            return f"{label}: {fields[field]['message']}"
    if status == 429:
        return "Too many attempts. Wait a minute and try again."
    return "Sign-up is unavailable right now. Try again in a minute."


def request_reset(email: str, client_ip: str) -> None:
    # Same answer whether or not the account exists, so the page can't be used to probe emails.
    pb_call("/api/collections/users/request-password-reset", {"email": email}, client_ip=client_ip)


# ── Pages ────────────────────────────────────────────────────────────────────

_SLOT = "<!-- content: filled in by webauth/server.py -->"
esc = html.escape


def page(content: str) -> bytes:
    try:
        with open(os.path.join(WEB_ROOT, "login.html"), "r", encoding="utf-8") as f:
            return f.read().replace(_SLOT, content).encode("utf-8")
    except OSError:
        return (f"<!doctype html><meta charset=utf-8><title>Ares Empire</title>"
                f"<body style='background:#000;color:#e9c86b;font-family:sans-serif;text-align:center;padding-top:18vh'>"
                f"<h1 style='letter-spacing:.2em'>ARES EMPIRE</h1>{content}").encode("utf-8")


def err(message: str) -> str:
    return f'<p class="err">{esc(message)}</p>' if message else ""


def welcome_page(error: str = "") -> bytes:
    return page(f"""<p class="sub">One account for every service of the empire</p>
    {err(error)}
    <a class="button" href="/login/email">Log in</a>
    <p class="alt">New account? <a href="/signup">Sign up</a></p>""")


def login_page(error: str = "", email: str = "") -> bytes:
    return page(f"""<p class="sub">Log in with your Empire account</p>
    {err(error)}
    <form method="POST" action="/login">
      <input type="email" name="email" placeholder="Email" aria-label="Email" autocomplete="username" value="{esc(email)}" required {'' if email else 'autofocus'} />
      <input type="password" name="password" placeholder="Password" aria-label="Password" autocomplete="current-password" required {'autofocus' if email else ''} />
      <button type="submit">Log in</button>
    </form>
    <p class="alt"><a href="/forgot">Forgot password?</a> · <a href="/signup">Sign up</a></p>""")


def signup_page(error: str = "", email: str = "") -> bytes:
    return page(f"""<p class="sub">Create your Empire account</p>
    {err(error)}
    <form method="POST" action="/signup">
      <input type="email" name="email" placeholder="Email" aria-label="Email" autocomplete="username" value="{esc(email)}" required autofocus />
      <input type="password" name="password" placeholder="Password (8+ characters)" aria-label="Password" autocomplete="new-password" minlength="8" required />
      <input type="password" name="confirm" placeholder="Repeat password" aria-label="Repeat password" autocomplete="new-password" minlength="8" required />
      <button type="submit">Sign up</button>
    </form>
    <p class="alt">Already have an account? <a href="/login/email">Log in</a></p>""")


def signup_done_page(email: str) -> bytes:
    return page(f"""<p class="sub">Almost there</p>
    <p class="note">We sent a confirmation link to <b>{esc(email)}</b>. Click it, then your account
    waits for approval. You get an email as soon as it's approved.</p>
    <p class="alt"><a href="/login">Back</a></p>""")


def forgot_page() -> bytes:
    return page("""<p class="sub">Reset your password</p>
    <form method="POST" action="/forgot">
      <input type="email" name="email" placeholder="Email" aria-label="Email" autocomplete="username" required autofocus />
      <button type="submit">Send reset link</button>
    </form>
    <p class="alt"><a href="/login/email">Back to log in</a></p>""")


def forgot_done_page() -> bytes:
    return page("""<p class="sub">Check your email</p>
    <p class="note">If an account exists for that email, a link to set a new password is on its way.</p>
    <p class="alt"><a href="/login/email">Back to log in</a></p>""")


def handoff_page(url: str, token: str) -> bytes:
    """Carries the Empire token to a province by POST (never in a URL), submitted automatically."""
    return page(f"""<p class="sub">Entering…</p>
    <form id="handoff" method="POST" action="{esc(url)}/sso">
      <input type="hidden" name="token" value="{esc(token)}" />
      <noscript><button type="submit">Continue</button></noscript>
    </form>
    <script>document.getElementById("handoff").submit();</script>""")


# ── HTTP ─────────────────────────────────────────────────────────────────────

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_ROOT, **kwargs)

    def log_message(self, fmt, *args):  # quieter logs
        sys.stderr.write(f"{self.address_string()} - {fmt % args}\n")

    def _client_ip(self) -> str:
        # Caddy sets X-Forwarded-For to the visitor's address; the last entry is the one it added.
        fwd = self.headers.get("X-Forwarded-For", "")
        return fwd.split(",")[-1].strip() if fwd else self.client_address[0]

    def _redirect(self, location: str, cookie: str | None = None) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
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

    def _token(self) -> str:
        return session_token(self.headers.get("Cookie"))

    def _authed(self) -> bool:
        return token_ok(self._token())

    def _form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > MAX_FORM_BYTES:
            return {}
        body = self.rfile.read(length).decode("utf-8", "replace")
        return {k: v[0] for k, v in parse_qs(body).items()}

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path
        if path in ("/login", "/login/email", "/signup", "/forgot"):
            if self._authed():
                return self._redirect("/")
            return self._send_html({"/login": welcome_page, "/login/email": login_page,
                                    "/signup": signup_page, "/forgot": forgot_page}[path]())
        if path == "/logout":
            return self._redirect("/login", cookie=clear_cookie())
        if path == "/sso":
            # hand a logged-in visitor to a province
            if not self._authed():
                return self._redirect("/login")
            province = PROVINCES.get((parse_qs(url.query).get("to") or [""])[0])
            if not province:
                return self._redirect("/")  # unknown → never an open redirect
            if province["handoff"]:
                return self._send_html(handoff_page(province["url"], self._token()))
            return self._redirect(province["url"] + "/")
        if path not in OPEN_PATHS and not self._authed():
            return self._redirect("/login")
        if path == "/api/empire":
            return self._send_state()
        return super().do_GET()

    def do_HEAD(self):
        path = urlparse(self.path).path
        if path not in OPEN_PATHS and not self._authed():
            return self._redirect("/login")
        return super().do_HEAD()

    def do_POST(self):
        path = urlparse(self.path).path
        form = self._form()
        email = form.get("email", "").strip()
        ip = self._client_ip()
        if path == "/login":
            token, error = login(email, form.get("password", ""), ip)
            if token:
                return self._redirect("/", cookie=session_cookie(token))
            return self._send_html(login_page(error, email), status=HTTPStatus.UNAUTHORIZED)
        if path == "/signup":
            error = signup(email, form.get("password", ""), form.get("confirm", ""), ip)
            if error:
                return self._send_html(signup_page(error, email), status=HTTPStatus.BAD_REQUEST)
            return self._send_html(signup_done_page(email))
        if path == "/forgot":
            if email:
                request_reset(email, ip)
            return self._send_html(forgot_done_page())
        self.send_error(HTTPStatus.NOT_FOUND)

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


def main() -> None:
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    sys.stderr.write(f"Ares Empire web serving {WEB_ROOT} on {HOST}:{PORT}, accounts at {AUTH_URL}\n")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
