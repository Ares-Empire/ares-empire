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
import posixpath
import re
import sys
import threading
import urllib.error
import urllib.request
from http import HTTPStatus
from http.client import HTTPException
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from time import time
from urllib.parse import parse_qs, urlencode, urlparse

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
# empire_sync. Missing → 503 and the frontend uses its embedded seed.
STATE_PATH = os.environ.get(
    "EMPIRE_STATE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "state.json"))
CATALOG_PATH = os.path.join(os.path.dirname(__file__), "catalog.json")
# Plain JSON snapshot of web/app/empire-data.js, usable without a JS runtime.
PULSE_URLS = {"aresium": "https://aresium.de/api/pulse"}
LIVE_CACHE_SECS = 60

# Reachable without a session: the login pages and the images they show.
# Exact paths only. Prefix matching ("/brand/") let "/brand/../index.html" past the login (2026-10-22).
# The iPhone apps load province marks with their Bearer token (they have no cookie). Images only: the normalised
# path must stay under /brand/ and end in an image type, so "/brand/../index.html" is not a way to a page.
BRAND_IMAGE_TYPES = (".webp", ".png", ".jpg", ".jpeg", ".svg")


def is_brand_image(path: str) -> bool:
    clean = posixpath.normpath(path)
    return clean.startswith("/brand/") and clean == path and clean.lower().endswith(BRAND_IMAGE_TYPES)


OPEN_PATHS = frozenset({"/login", "/login/email", "/signup", "/forgot", "/logout", "/favicon.ico",
                        "/brand/ares-bust-login.webp", "/brand/ares-bust-icon.png"})


# ── Talking to the accounts server ───────────────────────────────────────────

def pb_call(path: str, body: dict | None = None, token: str | None = None,
            client_ip: str | None = None, method: str = "POST") -> tuple[int, dict]:
    """Call PocketBase; status 0 means unreachable or an unreadable response."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    if client_ip:
        headers["X-Forwarded-For"] = client_ip  # so PocketBase rate-limits per visitor, not per hub
    req = urllib.request.Request(AUTH_URL + path, method=method, headers=headers,
                                 data=json.dumps(body or {}).encode() if method in ("POST", "PATCH") else None)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read()
            data = json.loads(raw) if raw else {}
            return (r.status, data) if isinstance(data, dict) else (0, {})
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read() or b"{}")
            return e.code, data if isinstance(data, dict) else {}
        except (OSError, ValueError, HTTPException):
            return e.code, {}
        finally:
            e.close()
    except (OSError, ValueError, HTTPException):
        return 0, {}


def has_access(record: dict | None) -> bool:
    return (isinstance(record, dict) and record.get("approved") is True
            and isinstance(record.get("services"), list) and SERVICE in record["services"])


_cache: dict[str, tuple[dict, float]] = {}
_cache_lock = threading.Lock()


def token_access(token: str, client_ip: str | None = None) -> dict:
    """Keep token rejection, lack of access, and outages distinct, as in Aresium."""
    unauthenticated = {"outcome": "denied", "status": 401, "error": "unauthenticated"}
    forbidden = {"outcome": "denied", "status": 403, "error": "This account has no access to Ares Empire."}
    unavailable = {"outcome": "unavailable", "status": 503,
                   "error": "Login service unavailable, try again in a minute."}
    if not token:
        return unauthenticated
    key = hashlib.sha256(token.encode()).hexdigest()
    now = time()
    with _cache_lock:
        hit = _cache.get(key)
    if hit and hit[1] > now:
        return hit[0]
    status, data = pb_call("/api/collections/users/auth-refresh", token=token, client_ip=client_ip)
    if status == 200:
        record = data.get("record")
        if not isinstance(record, dict) or not isinstance(record.get("id"), str) or not record["id"]:
            return unavailable
        access = {"outcome": "allowed", "record": record} if has_access(record) else forbidden
    elif status in (400, 401):
        access = unauthenticated
    elif status == 403:
        access = forbidden
    else:
        return unavailable  # Never cache outages, rate limits, or unexpected replies.
    with _cache_lock:
        if len(_cache) >= 1000:
            _cache.clear()
        _cache[key] = (access, now + CHECK_CACHE_SECS)
    return access


def forget_token(token: str) -> None:
    with _cache_lock:
        _cache.pop(hashlib.sha256(token.encode()).hexdigest(), None)


class APIError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message


def load_state() -> dict:
    # data/state.json is written by empire_sync. Without it the API answers 503 and the website falls back to its
    # embedded seed (web/app/empire-data.js), the only copy of the seed.
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("projects"), list):
            return data
    except (OSError, ValueError):
        pass
    raise APIError(503, "Hub data unavailable, try again in a minute.")


def load_catalog() -> dict:
    with open(CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)


_live_cache: dict[tuple[str, str], tuple[str | None, float]] = {}
_live_lock = threading.Lock()


def live_line(slug: str, account_id: str, token: str) -> str | None:
    url = PULSE_URLS.get(slug)
    if not url:
        return None
    key = (account_id, slug)
    with _live_lock:
        hit = _live_cache.get(key)
    if hit and hit[1] > time():
        return hit[0]
    line = None
    try:
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
        with urllib.request.urlopen(req, timeout=2) as r:
            data = json.load(r)
            if r.status == 200 and isinstance(data, dict) and isinstance(data.get("line"), str):
                line = data["line"]
    except urllib.error.HTTPError as e:
        e.close()
    except (OSError, ValueError, HTTPException):
        pass  # Pulse failures never turn into hub errors.
    with _live_lock:
        if len(_live_cache) >= 1000:
            _live_cache.clear()
        _live_cache[key] = (line, time() + LIVE_CACHE_SECS)
    return line


def account_ring(record: dict) -> list[str]:
    ring = record.get("ring")
    return list(dict.fromkeys(s for s in ring if isinstance(s, str))) if isinstance(ring, list) else []


def require_pb(status: int) -> None:
    if 200 <= status < 300:
        return
    if status in (400, 401, 403, 404):
        raise APIError(status, {400: "Invalid account request.", 401: "unauthenticated",
                                403: "Forbidden.", 404: "Account not found."}[status])
    raise APIError(503, "Account service unavailable, try again in a minute.")


def pending_accounts(token: str, client_ip: str, count_only: bool = False):
    items = []
    page = 1
    while True:
        query = urlencode({"filter": "approved = false", "sort": "created,id", "page": page,
                           "perPage": 1 if count_only else 500,
                           "fields": "id,email,name,created"})
        status, data = pb_call("/api/collections/users/records?" + query, token=token,
                               client_ip=client_ip, method="GET")
        require_pb(status)
        if not isinstance(data.get("items"), list) or not isinstance(data.get("totalItems"), int):
            raise APIError(503, "Account service returned an unreadable response.")
        if count_only:
            return data["totalItems"]
        items.extend({k: item.get(k, "") for k in ("id", "email", "name", "created")}
                     for item in data["items"])
        if page >= data.get("totalPages", 1):
            return items
        page += 1


def empire_data(record: dict, token: str, client_ip: str) -> dict:
    state, catalog = load_state(), load_catalog()
    admin = record.get("admin") is True
    ring = set(account_ring(record)) & catalog.keys()

    def province(project):
        slug = project["slug"]
        entry = catalog.get(slug, {})
        return {**project, "state": "open" if admin else entry["users"],
                "app": entry.get("app"), "live": live_line(slug, record["id"], token)}

    projects = state.get("projects", [])
    # Keep the version-1 field names and all province metadata.
    return {"version": 2, "me": {"id": record["id"], "name": record.get("name", ""), "admin": admin},
            "projects": [province(p) for p in projects if admin or p["slug"] in ring],
            "addable": [] if admin else [province(p) for p in projects
                                         if p["slug"] in catalog and p["slug"] not in ring],
            "chronicle": [e for e in state.get("chronicle", []) if admin or e.get("project") in ring],
            "ideas": state.get("ideas", []) if admin else [],
            "pending": pending_accounts(token, client_ip, count_only=True) if admin else 0}


def change_ring(record: dict, token: str, client_ip: str, body: dict) -> dict:
    if set(body) not in ({"add"}, {"remove"}):
        raise APIError(400, "Send exactly one province to add or remove.")
    action, slug = next(iter(body.items()))
    if not isinstance(slug, str) or slug not in load_catalog():
        raise APIError(400, "Unknown catalog province.")
    ring = account_ring(record)
    if action == "add" and slug not in ring:
        ring.append(slug)
    elif action == "remove":
        ring = [s for s in ring if s != slug]
    status, updated = pb_call("/api/collections/users/records/" + record["id"], {"ring": ring},
                              token=token, client_ip=client_ip, method="PATCH")
    require_pb(status)
    if updated.get("id") != record["id"] or updated.get("ring") != ring:
        raise APIError(503, "Account service returned an unreadable response.")
    forget_token(token)  # The next request must not reuse the old ring from auth-refresh.
    return empire_data({**record, "ring": ring}, token, client_ip)


def decide_approval(account_id: str, token: str, client_ip: str, body: dict) -> dict:
    if not re.fullmatch(r"[a-zA-Z0-9]{15}", account_id):
        raise APIError(400, "Invalid account id.")
    if body != {"approve": True} and body != {"decline": True}:
        raise APIError(400, "Send approve: true or decline: true.")
    # bool is intentional: JSON numbers must not count as `true`.
    if next(iter(body.values())) is not True:
        raise APIError(400, "Send approve: true or decline: true.")
    path = "/api/collections/users/records/" + account_id
    if "approve" in body:
        status, _ = pb_call(path, {"approved": True, "services": [SERVICE]},
                            token=token, client_ip=client_ip, method="PATCH")
    else:
        # PocketBase enforces approved = false atomically on DELETE.
        status, _ = pb_call(path, token=token, client_ip=client_ip, method="DELETE")
    require_pb(status)
    return {"ok": True}


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


def login(email: str, password: str, client_ip: str) -> tuple[str | None, str, int]:
    """Returns (token, message, HTTP status), preserving auth failure categories."""
    status, data = pb_call("/api/collections/users/auth-with-password",
                           {"identity": email, "password": password}, client_ip=client_ip)
    if status == 200:
        record = data.get("record")
        if (not isinstance(data.get("token"), str) or not data["token"]
                or not isinstance(record, dict) or not isinstance(record.get("id"), str) or not record["id"]):
            return None, "Login is unavailable right now. Try again in a minute.", 503
        if has_access(record):
            return data["token"], "", 200
        return None, "This account has no access to Ares Empire.", 403
    if status == 400:
        return None, "Wrong email or password.", 401
    if status == 401:
        return None, "Wrong email or password.", 401
    if status == 403:  # right password, but not verified and/or not approved yet
        return None, "This account isn't active yet. Confirm your email, then wait for approval.", 403
    if status == 429:
        return None, "Too many attempts. Wait a minute and try again.", 503
    return None, "Login is unavailable right now. Try again in a minute.", 503


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
        return token_access(self._token(), self._client_ip())["outcome"] == "allowed"

    def _bearer_ok(self) -> bool:
        # the iPhone apps send the Empire token as "Authorization: Bearer <token>" (API only)
        match = re.fullmatch(r"Bearer\s+(\S+)", self.headers.get("Authorization", ""), re.I)
        return bool(match) and token_access(match[1], self._client_ip())["outcome"] == "allowed"

    def _web_gate(self) -> bool:
        access = token_access(self._token(), self._client_ip())
        if access["outcome"] == "allowed":
            return True
        if access["status"] == 401:
            self._redirect("/login")
        else:
            self._send_html(page(err(access["error"])), access["status"])
        return False

    def _json_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise APIError(400, "Invalid content length.")
        if length > MAX_FORM_BYTES:
            raise APIError(413, "Request too large.")
        if length <= 0:
            raise APIError(400, "A JSON object is required.")
        try:
            body = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeError):
            raise APIError(400, "Invalid JSON.")
        if not isinstance(body, dict):
            raise APIError(400, "A JSON object is required.")
        return body

    def _api(self, path: str) -> None:
        try:
            if "Authorization" in self.headers:
                match = re.fullmatch(r"Bearer\s+(\S+)", self.headers["Authorization"], re.I)
                token = match[1] if match else ""
            else:
                token = self._token()
            ip = self._client_ip()
            access = token_access(token, ip)
            if access["outcome"] != "allowed":
                raise APIError(access["status"], access["error"])
            record = access["record"]
            if path == "/api/empire/approvals" or path.startswith("/api/empire/approvals/"):
                if record.get("admin") is not True:
                    raise APIError(403, "Administrator access required.")
            if self.command in ("GET", "HEAD") and path == "/api/empire":
                return self._send_state(record, token, ip)
            if self.command in ("GET", "HEAD") and path == "/api/empire/approvals":
                data = pending_accounts(token, ip)
            elif self.command == "POST" and path == "/api/empire/ring":
                data = change_ring(record, token, ip, self._json_body())
            elif self.command == "POST" and path.startswith("/api/empire/approvals/"):
                data = decide_approval(path.rsplit("/", 1)[1], token, ip, self._json_body())
            else:
                raise APIError(404, "Unknown API route.")
            self._send_json(json.dumps(data).encode())
        except APIError as e:
            self._send_json(json.dumps({"error": e.message}).encode(), e.status)

    def _form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > MAX_FORM_BYTES:
            return {}
        body = self.rfile.read(length).decode("utf-8", "replace")
        return {k: v[0] for k, v in parse_qs(body).items()}

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path
        if path == "/api/empire" or path.startswith("/api/empire/"):
            return self._api(path)
        if path in ("/login", "/login/email", "/signup", "/forgot"):
            if self._authed():
                return self._redirect("/")
            return self._send_html({"/login": welcome_page, "/login/email": login_page,
                                    "/signup": signup_page, "/forgot": forgot_page}[path]())
        if path == "/logout":
            return self._redirect("/login", cookie=clear_cookie())
        if path == "/sso":
            # hand a logged-in visitor to a province
            if not self._web_gate():
                return
            province = PROVINCES.get((parse_qs(url.query).get("to") or [""])[0])
            if not province:
                return self._redirect("/")  # unknown → never an open redirect
            if province["handoff"]:
                return self._send_html(handoff_page(province["url"], self._token()))
            return self._redirect(province["url"] + "/")
        if is_brand_image(path) and self.headers.get("Authorization") and self._bearer_ok():
            return super().do_GET()
        if path not in OPEN_PATHS and not self._web_gate():
            return
        return super().do_GET()

    def do_HEAD(self):
        path = urlparse(self.path).path
        if path == "/api/empire" or path.startswith("/api/empire/"):
            return self._api(path)
        if path not in OPEN_PATHS and not self._web_gate():
            return
        return super().do_HEAD()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/empire" or path.startswith("/api/empire/"):
            return self._api(path)
        form = self._form()
        email = form.get("email", "").strip()
        ip = self._client_ip()
        if path == "/login":
            token, error, status = login(email, form.get("password", ""), ip)
            if token:
                return self._redirect("/", cookie=session_cookie(token))
            return self._send_html(login_page(error, email), status=status)
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

    def _send_state(self, record: dict, token: str, client_ip: str) -> None:
        self._send_json(json.dumps(empire_data(record, token, client_ip)).encode())

    def _send_json(self, body: bytes, status: int = HTTPStatus.OK) -> None:
        self.send_response(status)
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
