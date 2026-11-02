#!/usr/bin/env python3
"""Ares Empire web server — static files for the hub, behind a login with Empire accounts.

Accounts live in PocketBase (https://auth.ares-empire.de, see docs/ACCOUNTS.md). This server
talks to it on localhost: log in, sign up, password reset. The session cookie holds the
Empire token; every request re-checks it (approved, has the "empire" service) with a short
cache, so un-approving someone locks them out within a minute. The privacy policy and imprint (webauth/legal.py) and
the contact pages of the Empire and Arestemis (webauth/contact.py) are open to everyone. Stdlib only.

Config (env, from .env — never committed):
  EMPIRE_AUTH_URL   PocketBase base URL (default http://127.0.0.1:8090)
  WEB_ROOT          dir to serve (default: web)        HOST / PORT
  LEGAL_PREVIEW     1 = serve legal pages that are still drafts, and the contact pages without their published privacy
                    policy (local preview only, never on the server)
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
import traceback
import urllib.error
import urllib.request
from http import HTTPStatus
from http.client import HTTPException
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from time import time
from urllib.parse import parse_qs, urlencode, urlparse

# The systemd unit also supports running this file directly from outside the repo root.
if not __package__:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from empire_language import request_language
from webauth import contact, legal, owner
from webauth.texts import text

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
# Which provinces other accounts may ask for (docs/API-EMPIRE.md → Catalog).
CATALOG_PATH = os.path.join(os.path.dirname(__file__), "catalog.json")
# The iPhone app of each province, whoever may see it (docs/API-EMPIRE.md → Apps): its URL scheme (the Empire app opens
# the province in its app when it is installed) and its install link (TestFlight public link while testing, the App
# Store later; null until there is one).
APPS_PATH = os.path.join(os.path.dirname(__file__), "apps.json")
PULSE_URLS = {"aresium": "https://aresium.de/api/pulse"}
# Every other province gets its line from Aresus, the watchtower (one overview per account and minute, asked with the
# visitor's own token; accounts Aresus does not let in get no line: it needs the "aresus" service and its owner
# allowlist). Same host, so localhost.
ARESUS_OVERVIEW_URL = os.environ.get("ARESUS_OVERVIEW_URL", "http://127.0.0.1:8098/api/aresus/overview")
LIVE_CACHE_SECS = 60

# Reachable without a session: the login pages and the images they show.
# Exact paths only. Prefix matching ("/brand/") let "/brand/../index.html" past the login (2026-10-22).
# The iPhone apps load province marks with their Bearer token (they have no cookie). Images only: the normalised
# path must stay under /brand/ and end in an image type, so "/brand/../index.html" is not a way to a page.
BRAND_IMAGE_TYPES = (".webp", ".png", ".jpg", ".jpeg", ".svg")


def is_brand_image(path: str) -> bool:
    clean = posixpath.normpath(path)
    return clean.startswith("/brand/") and clean == path and clean.lower().endswith(BRAND_IMAGE_TYPES)


# The legal pages (/datenschutz, /privacy, /impressum, /imprint) and the contact pages (/contact, /kontakt,
# /arestemis/contact, /arestemis/kontakt) are open too: they are answered before the gate (webauth/legal.py,
# webauth/contact.py), and the files they load are listed here. The contact forms post from the browser straight to the
# account server, not through this server.
# The login page's fonts are served from here (web/fonts, no font service), so they are open as well.
LOGIN_FONTS = frozenset({"/fonts/fonts.css", "/fonts/SpaceGrotesk-Variable.ttf", "/fonts/JetBrainsMono-Variable.ttf",
                         "/fonts/Cinzel-Variable.ttf"})
OPEN_PATHS = frozenset({"/login", "/login/email", "/signup", "/forgot", "/logout", "/favicon.ico",
                        "/brand/ares-bust-login.webp", "/brand/ares-bust-icon.png"}) | legal.ASSET_PATHS | LOGIN_FONTS \
    | contact.ASSET_PATHS

# The public demo (www.ares-empire.de/demo, Patrik 2026-10-27): the hub for anyone, without an account. It is
# index.html with the demo's words (app/samples/demo-empire.js) in place of the real seed, and app/empire-api.js loads
# the made-up guest (app/samples/empire.demo.json); tools/empire_samples.py --web writes both. The page's own files are
# open for it, read from index.html so a new script is covered; the real seed (app/empire-data.js: the provinces,
# expansions and chronicle) and the other samples stay behind the login.
DEMO_SEED_SCRIPT = 'src="app/empire-data.js"'
DEMO_WORDS_SCRIPT = 'src="app/samples/demo-empire.js"'
DEMO_SAMPLES = frozenset({"/app/samples/empire.demo.json", "/app/samples/demo-empire.js"})
DEMO_DIRS = ("/vendor/", "/fonts/", "/brand/")


def _index_html() -> str:
    with open(os.path.join(WEB_ROOT, "index.html"), encoding="utf-8") as f:
        return f.read()


def demo_page() -> bytes:
    page = _index_html()
    if DEMO_SEED_SCRIPT not in page:
        raise RuntimeError("index.html no longer loads app/empire-data.js: the demo would load no words")
    return page.replace(DEMO_SEED_SCRIPT, DEMO_WORDS_SCRIPT).encode("utf-8")


def is_demo_file(path: str) -> bool:
    """A file the demo page loads: index.html's own scripts and styles except the real seed, the demo's two samples,
    and files (never a folder, so no listing) in the shared folders of pictures, fonts and libraries."""
    if path in DEMO_SAMPLES:
        return True
    if path.startswith(DEMO_DIRS):
        return ".." not in path and not path.endswith("/") and os.path.isfile(os.path.join(WEB_ROOT, path.lstrip("/")))
    try:
        page = _index_html()
    except OSError:
        return False
    page_files = {"/" + ref for ref in re.findall(r'(?:src|href)="([^":?#]+)"', page)}
    return path in page_files - {"/app/empire-data.js"}


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


UNAUTHENTICATED = "Please log in again."


def token_access(token: str, client_ip: str | None = None) -> dict:
    """Keep token rejection, lack of access, and outages distinct, as in Aresium."""
    unauthenticated = {"outcome": "denied", "status": 401, "error": UNAUTHENTICATED}
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


def log(message: str) -> None:
    sys.stderr.write(message + "\n")


# Every error of the JSON API is {"error": <a sentence in the request's language>, "code": <one of these>}
# (docs/API-EMPIRE.md → Errors). Codes are stable English words that clients act on; they are never translated.
# By status; a 403 on an admin route is admin_only instead (the account is not an admin).
CODES = {400: "bad_request", 401: "unauthorized", 403: "no_access", 404: "not_found",
         413: "bad_request", 500: "server_error", 503: "unavailable"}
ERROR_CODES = frozenset(CODES.values()) | {"admin_only"}
SERVER_ERROR = "Something went wrong on the server. Try again later."


class APIError(Exception):
    def __init__(self, status: int, message: str, code: str | None = None):
        self.status = status
        self.message = message
        self.code = code or CODES[status]


# ── Hub data in the contract's shape ─────────────────────────────────────────
# data/state.json is written by empire_sync and edited by hand (the chronicle, EMPIRE.md), so it can miss a field or
# hold a wrong type. hub_state() is the one place that brings it to the contract (docs/API-EMPIRE.md → Hub data):
# every field with its type, the documented default for what is missing, entries without what identifies them skipped.
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
PLACEHOLDER_LOGO = "brand/ares-bust.webp"  # the empire crest, as empire_sync gives a new province


def _string(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _strings(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _dated(entry: object, with_project: bool) -> dict | None:
    """A chronicle or changelog entry {at, (project,) text}; None without a date or a text."""
    if not isinstance(entry, dict) or not _string(entry.get("at")) or not _string(entry.get("text")):
        return None
    if with_project:
        return {"at": entry["at"], "project": entry.get("project") if isinstance(entry.get("project"), str) else None,
                "text": entry["text"]}
    return {"at": entry["at"], "text": entry["text"]}


def _province(project: object) -> dict | None:
    """A province's version-1 fields in the contract's shape; None without a usable slug."""
    if not isinstance(project, dict) or not isinstance(project.get("slug"), str) or not SLUG.fullmatch(project["slug"]):
        return None
    slug = project["slug"]
    detail = project.get("detail") if isinstance(project.get("detail"), dict) else {}
    changelog = detail.get("changelog") if isinstance(detail.get("changelog"), list) else []
    return {
        "slug": slug,
        "name": _string(project.get("name")) or slug[:1].upper() + slug[1:],
        "url": _string(project.get("url")),
        "logo": _string(project.get("logo")) or PLACEHOLDER_LOGO,
        "status": _string(project.get("status")),
        "domain": _string(project.get("domain")),
        "blurb": _string(project.get("blurb")),
        "detail": {"about": _string(detail.get("about")), "features": _strings(detail.get("features")),
                   "setup": _string(detail.get("setup")), "wip": _strings(detail.get("wip")),
                   "ideas": _strings(detail.get("ideas")),
                   "changelog": [e for e in (_dated(entry, False) for entry in changelog) if e]},
    }


def hub_state(raw: dict) -> dict:
    """state.json → {projects, ideas, chronicle} exactly as the contract describes them; one log line for what was
    skipped."""
    projects, skipped = [], []
    for number, project in enumerate(raw.get("projects") or [], 1):
        province = _province(project)
        if province is None:
            skipped.append(f"province {number} (no usable slug)")
        elif any(p["slug"] == province["slug"] for p in projects):
            skipped.append(f"province {number} (slug {province['slug']} again)")
        else:
            projects.append(province)
    chronicle = raw.get("chronicle") if isinstance(raw.get("chronicle"), list) else []
    entries = [e for e in (_dated(entry, True) for entry in chronicle) if e]
    if len(entries) < len(chronicle):
        skipped.append(f"{len(chronicle) - len(entries)} chronicle entries (no date or text)")
    ideas = []
    for idea in raw.get("ideas") if isinstance(raw.get("ideas"), list) else []:
        if isinstance(idea, dict) and _string(idea.get("title")):
            ideas.append({"title": idea["title"], "note": _string(idea.get("note"))})
        else:
            skipped.append("an idea (no title)")
    if skipped:
        log("state.json: skipped " + "; ".join(skipped))
    return {"projects": projects, "ideas": ideas, "chronicle": entries}


def read_state() -> dict:
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


def load_state() -> dict:
    return hub_state(read_state())


def load_catalog() -> dict:
    with open(CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)


CATALOG_STATES = ("open", "coming-soon")


def catalog_states(catalog: object) -> dict[str, str]:
    """slug → "open" | "coming-soon" for the provinces open to other accounts; any other entry counts as private."""
    if not isinstance(catalog, dict):
        return {}
    return {slug: entry["users"] for slug, entry in catalog.items()
            if isinstance(entry, dict) and entry.get("users") in CATALOG_STATES}


def load_apps() -> dict[str, dict[str, str | None]]:
    """apps.json as slug → {"scheme", "install"}. A value that is not a non-empty text counts as None, and so does an
    install link that is not https (a TestFlight or App Store page)."""
    with open(APPS_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    apps = {}
    for slug, app in raw.items() if isinstance(raw, dict) else ():
        if not isinstance(app, dict):
            continue
        scheme, install = app.get("scheme"), app.get("install")
        apps[slug] = {"scheme": scheme if isinstance(scheme, str) and scheme else None,
                      "install": install if isinstance(install, str) and install.startswith("https://") else None}
    return apps


_live_cache: dict[tuple[str, str, str], tuple[str | dict[str, str] | None, float]] = {}
_live_lock = threading.Lock()


def _fetch_json(url: str, token: str, language: str):
    """GET with the visitor's token; None on any failure (live lines never turn into hub errors)."""
    try:
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token,
                                                  "Accept-Language": language})
        with urllib.request.urlopen(req, timeout=2) as r:
            data = json.load(r)
            return data if r.status == 200 else None
    except urllib.error.HTTPError as e:
        e.close()
    except (OSError, ValueError, HTTPException):
        pass
    return None


def aresus_lines(account_id: str, token: str, language: str = "en") -> dict[str, str]:
    """slug -> Aresus's line with an issue prefix, cached per account and language."""
    key = (account_id, "__aresus__", language)
    with _live_lock:
        hit = _live_cache.get(key)
    if hit and hit[1] > time():
        return hit[0]
    lines: dict[str, str] = {}
    data = _fetch_json(ARESUS_OVERVIEW_URL, token, language)
    provinces = data.get("provinces") if isinstance(data, dict) else None
    for p in provinces if isinstance(provinces, list) else []:
        if isinstance(p, dict) and isinstance(p.get("slug"), str) and isinstance(p.get("line"), str) and p["line"]:
            lines[p["slug"]] = (text("Issue: ", language) if p.get("state") == "issue" else "") + p["line"]
    with _live_lock:
        if len(_live_cache) >= 1000:
            _live_cache.clear()
        _live_cache[key] = (lines, time() + LIVE_CACHE_SECS)
    return lines


def live_line(slug: str, account_id: str, token: str, language: str = "en") -> str | None:
    url = PULSE_URLS.get(slug)
    if not url:
        return aresus_lines(account_id, token, language).get(slug)
    key = (account_id, slug, language)
    with _live_lock:
        hit = _live_cache.get(key)
    if hit and hit[1] > time():
        return hit[0]
    line = None
    data = _fetch_json(url, token, language)
    if isinstance(data, dict) and isinstance(data.get("line"), str):
        line = data["line"]
    with _live_lock:
        if len(_live_cache) >= 1000:
            _live_cache.clear()
        _live_cache[key] = (line, time() + LIVE_CACHE_SECS)
    return line


def strings_of(record: dict, field: str) -> list[str]:
    """A list field of an account record (services, requested) as its texts; anything else counts as empty."""
    value = record.get(field)
    return [s for s in value if isinstance(s, str)] if isinstance(value, list) else []


def require_pb(status: int, forbidden: str = "no_access") -> None:
    """Passes the account server's refusals on with their status and code; everything else is 503 unavailable.
    `forbidden` is the code of a 403: no_access, or admin_only on the admin routes."""
    if 200 <= status < 300:
        return
    if status in (400, 401, 403, 404):
        raise APIError(status, {400: "Invalid account request.", 401: UNAUTHENTICATED,
                                403: "Forbidden.", 404: "Account not found."}[status],
                       forbidden if status == 403 else None)
    raise APIError(503, "Account service unavailable, try again in a minute.")


# What waits for Patrik: new sign-ups, and approved accounts that asked for more apps (docs/ACCOUNTS.md → Accounts in
# every app). `requested` holds only apps the account does not have yet (the account server keeps it so).
WAITING = "approved = false || requested:length > 0"


def pending_accounts(token: str, client_ip: str, count_only: bool = False):
    """The accounts waiting for Patrik, each {id, email, name, created, requested, approved, verified} (verified: the
    email address is confirmed; login needs it too), or with `count_only` how many there are."""
    items = []
    page = 1
    while True:
        query = urlencode({"filter": WAITING, "sort": "created,id", "page": page,
                           "perPage": 1 if count_only else 500,
                           "fields": "id,email,name,created,requested,approved,verified"})
        status, data = pb_call("/api/collections/users/records?" + query, token=token,
                               client_ip=client_ip, method="GET")
        require_pb(status, forbidden="admin_only")
        if not isinstance(data.get("items"), list) or not isinstance(data.get("totalItems"), int):
            raise APIError(503, "Account service returned an unreadable response.")
        if count_only:
            return data["totalItems"]
        items.extend({**{k: _string(item.get(k)) for k in ("id", "email", "name", "created")},
                      "requested": strings_of(item, "requested"), "approved": item.get("approved") is True,
                      "verified": item.get("verified") is True}
                     for item in data["items"] if isinstance(item, dict))
        if page >= data.get("totalPages", 1):
            return items
        page += 1


def pending_count(token: str, client_ip: str) -> int | None:
    """How many accounts wait for Patrik; None when the account server cannot say (the hub data comes without it)."""
    try:
        return pending_accounts(token, client_ip, count_only=True)
    except APIError as e:
        log(f"pending count unavailable: {e.status} {e.message}")
        return None


def empire_data(record: dict, token: str, client_ip: str, language: str = "en") -> dict:
    """GET /api/empire for this account (docs/API-EMPIRE.md). The ring (`projects`) is every province the account has:
    an admin every province, anyone else the provinces in its `services` (Patrik grants them). `addable` (the "+") is
    the rest of the catalog, each with whether the account has asked for it."""
    state, catalog, apps = load_state(), catalog_states(load_catalog()), load_apps()
    admin = record.get("admin") is True
    services, requested = set(strings_of(record, "services")), set(strings_of(record, "requested"))

    def granted(project):
        slug = project["slug"]
        app = apps.get(slug, {})
        return {**project, "state": "open", "live": live_line(slug, record["id"], token, language),
                "app": app.get("scheme"), "install": app.get("install"), "access": "granted"}

    def offered(project):
        # The account has no access to it, so the province is not asked for a live line, and the install link is
        # only for accounts that have the app.
        slug = project["slug"]
        return {**project, "state": catalog[slug], "live": None, "app": apps.get(slug, {}).get("scheme"),
                "install": None, "access": "requested" if slug in requested else "none"}

    projects = state["projects"]
    ring = [p for p in projects if admin or p["slug"] in services]
    ring_slugs = {p["slug"] for p in ring}
    return {"version": 2, "me": {"id": record["id"], "name": _string(record.get("name")), "admin": admin},
            "projects": [granted(p) for p in ring],
            "addable": [] if admin else [offered(p) for p in projects
                                         if p["slug"] in catalog and p["slug"] not in ring_slugs],
            "chronicle": [e for e in state["chronicle"] if admin or e["project"] in ring_slugs],
            "ideas": state["ideas"] if admin else [],
            "pending": pending_count(token, client_ip) if admin else 0}


def request_access(record: dict, token: str, client_ip: str, body: dict, language: str = "en") -> dict:
    """POST /api/empire/request {service}: the account asks for one app of the "+" (an `open` catalog province). It
    writes the account's own `requested` with its own token, like the apps' "Ask for access" (docs/ACCOUNTS.md →
    Accounts in every app); the account server then tells Patrik (pb_hooks/accounts.pb.js). Asking again for an app
    already asked for changes nothing. Answers the fresh GET /api/empire."""
    if set(body) != {"service"} or not isinstance(body["service"], str):
        raise APIError(400, "Say which app to ask for.")
    slug = body["service"]
    state = catalog_states(load_catalog()).get(slug)
    if state is None:
        raise APIError(400, "This app is not open to requests.")
    if state != "open":
        raise APIError(400, "This app is coming soon and cannot be requested yet.")
    if record.get("admin") is True:
        raise APIError(400, "This account already has this app.")  # an admin's ring is every province
    # Read the account itself (the record from auth-refresh may be a minute old), so what it has and has asked for
    # is current.
    path = "/api/collections/users/records/" + record["id"]
    status, account = pb_call(path + "?" + urlencode({"fields": "id,services,requested"}), token=token,
                              client_ip=client_ip, method="GET")
    require_pb(status)
    if account.get("id") != record["id"]:
        raise APIError(503, "Account service returned an unreadable response.")
    if slug in strings_of(account, "services"):
        raise APIError(400, "This account already has this app.")
    if slug not in strings_of(account, "requested"):
        # "requested+" adds this one app and keeps every other request, also one made since the read above.
        status, account = pb_call(path, {"requested+": [slug]}, token=token, client_ip=client_ip, method="PATCH")
        require_pb(status)
        # Granted in the meantime, the account server has moved it from requested to services: fine either way.
        if account.get("id") != record["id"] or slug not in strings_of(account, "requested") + strings_of(
                account, "services"):
            raise APIError(503, "Account service returned an unreadable response.")
    forget_token(token)  # The next GET /api/empire must not reuse the old services and requested from auth-refresh.
    return empire_data({**record, "services": strings_of(account, "services"),
                        "requested": strings_of(account, "requested")}, token, client_ip, language)


def decision_of(body: dict) -> tuple[str, list[str] | None]:
    """{approve: true} or {decline: true}, optionally with `requested` (the apps Patrik saw on the card) →
    ("approve" | "decline", those apps or None)."""
    action = {key: value for key, value in body.items() if key != "requested"}
    # `is True`: JSON numbers must not count as true (in Python 1 == True).
    if set(action) not in ({"approve"}, {"decline"}) or next(iter(action.values())) is not True:
        raise APIError(400, "Send approve: true or decline: true.")
    seen = body.get("requested")
    if seen is not None and (not isinstance(seen, list) or not all(isinstance(s, str) for s in seen)):
        raise APIError(400, "requested must be a list of apps.")
    return next(iter(action)), seen


def decide_approval(account_id: str, token: str, client_ip: str, body: dict) -> dict:
    """Approve grants the account's requests (approved = true, services += them; the account server then drops them
    from requested). Decline deletes an account that is not approved yet, or withdraws an approved account's requests.
    Answers {ok, approvals, pending}: the list as GET /api/empire/approvals gives it, so the app needs no second call."""
    if not re.fullmatch(r"[a-zA-Z0-9]{15}", account_id):
        raise APIError(400, "Invalid account id.")
    action, seen = decision_of(body)
    path = "/api/collections/users/records/" + account_id
    status, account = pb_call(path + "?" + urlencode({"fields": "id,approved,requested"}),
                              token=token, client_ip=client_ip, method="GET")
    require_pb(status, forbidden="admin_only")
    if account.get("id") != account_id:
        raise APIError(503, "Account service returned an unreadable response.")
    current = strings_of(account, "requested")
    # The requests this decision is about: the account's requests as read just now, and when the app sends
    # `requested` (what Patrik saw on the card) only those he saw. A request made after he looked is neither granted
    # nor declined: it stays in `requested` and comes back in the list. The "+" and "-" forms change only the values
    # named, so a request made between this read and the write below stays as well.
    chosen = current if seen is None else [s for s in current if s in seen]
    if action == "approve":
        change = {"approved": True, "services+": chosen}
        unseen = [s for s in current if s not in chosen]
        if account.get("approved") is not True and unseen:
            # A first approval grants everything still in `requested` (accounts.pb.js), so what Patrik did not see
            # leaves it. An account that is not approved cannot log in, so only an admin can have changed it.
            change["requested-"] = unseen
        status, _ = pb_call(path, change, token=token, client_ip=client_ip, method="PATCH")
    elif account.get("approved") is True:
        status, _ = pb_call(path, {"requested-": chosen}, token=token, client_ip=client_ip, method="PATCH")
    else:
        # PocketBase enforces approved = false atomically on DELETE.
        status, _ = pb_call(path, token=token, client_ip=client_ip, method="DELETE")
    require_pb(status, forbidden="admin_only")
    try:
        approvals = pending_accounts(token, client_ip)
    except APIError as e:
        # The decision is made; only the fresh list is missing. The app then loads it with GET /api/empire/approvals.
        log(f"approvals list after a decision unavailable: {e.status} {e.message}")
        return {"ok": True, "approvals": None, "pending": None}
    return {"ok": True, "approvals": approvals, "pending": len(approvals)}


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
    # The website asks for the hub; it is in English (docs/LANGUAGES.md → Websites).
    status, data = pb_call("/api/collections/users/records",
                           {"email": email, "password": password, "passwordConfirm": confirm,
                            "requested": [SERVICE], "language": "en"},
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
    # Python's table lacks the font types on some versions (the legal pages' self-hosted font).
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".ttf": "font/ttf", ".woff2": "font/woff2"}

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

    def _send_html(self, body: bytes, status: int = 200, language: str = "en", csp: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Language", language)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if csp:
            self.send_header("Content-Security-Policy", csp)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_legal(self, path: str) -> None:
        """A legal page for everyone, logged in or not; 404 while it is missing or still a draft."""
        rendered = legal.render(path, WEB_ROOT, preview=legal.preview_enabled())
        if rendered is None:
            self.log_message("legal page %s not published (missing, or still holds a draft marker)", path)
            return self.send_error(HTTPStatus.NOT_FOUND)
        body, language = rendered
        self._send_html(body, language=language)

    def _send_contact(self, path: str, query: str) -> None:
        """A contact page for everyone, logged in or not, on the topic `?topic=` names; 404 while its privacy policy is
        not published. Its own Content-Security-Policy: no inline code, only this server and the account server."""
        topic = (parse_qs(query).get("topic") or [None])[0]
        rendered = contact.render(path, topic, WEB_ROOT, preview=legal.preview_enabled())
        if rendered is None:
            self.log_message("contact page %s not served (its privacy policy is not published)", path)
            return self.send_error(HTTPStatus.NOT_FOUND)
        body, language = rendered
        self._send_html(body, language=language, csp=contact.CSP)

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
        """Every answer of the JSON API: its data, or {"error": <sentence in the request's language>, "code"} with
        the status (docs/API-EMPIRE.md → Errors). An unexpected exception is logged with its traceback and answered
        500 server_error, never a dropped connection."""
        try:
            status, body = HTTPStatus.OK, json.dumps(self._api_data(path)).encode()
        except APIError as e:
            status, body = e.status, self._api_error(e.message, e.code)
        except Exception:
            log(f"{self.command} {path} failed:\n{traceback.format_exc().rstrip()}")
            status, body = HTTPStatus.INTERNAL_SERVER_ERROR, self._api_error(SERVER_ERROR, "server_error")
        self._send_json(body, status)

    def _api_error(self, message: str, code: str) -> bytes:
        return json.dumps({"error": text(message, self.language), "code": code}).encode()

    def _api_data(self, path: str):
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
                raise APIError(403, "Administrator access required.", "admin_only")
        if self.command in ("GET", "HEAD") and path == "/api/empire":
            return empire_data(record, token, ip, self.language)
        if self.command in ("GET", "HEAD") and path == "/api/empire/approvals":
            return pending_accounts(token, ip)
        if self.command == "POST" and path == "/api/empire/request":
            return request_access(record, token, ip, self._json_body(), self.language)
        if self.command == "POST" and path.startswith("/api/empire/approvals/"):
            return decide_approval(path.rsplit("/", 1)[1], token, ip, self._json_body())
        raise APIError(404, "Unknown API route.")

    @property
    def language(self) -> str:
        return request_language(self.headers.get("Accept-Language"))

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
        if path in legal.PAGES:
            return self._send_legal(path)
        if path in contact.PAGES:
            return self._send_contact(path, url.query)
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
        if path == "/demo/":
            return self._redirect("/demo")  # the page's paths are relative
        if path == "/demo":
            return self._send_html(demo_page())
        if is_demo_file(path):
            return super().do_GET()
        if path not in OPEN_PATHS and not self._web_gate():
            return
        return super().do_GET()

    def do_HEAD(self):
        url = urlparse(self.path)
        path = url.path
        if path == "/api/empire" or path.startswith("/api/empire/"):
            return self._api(path)
        if path in legal.PAGES:
            return self._send_legal(path)
        if path in contact.PAGES:
            return self._send_contact(path, url.query)
        if path == "/demo":
            return self._send_html(demo_page())
        if is_demo_file(path):
            return super().do_HEAD()
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

    def _send_json(self, body: bytes, status: int = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Language", self.language)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)


def main() -> None:
    try:
        owner.get_owner()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    sys.stderr.write(f"Ares Empire web serving {WEB_ROOT} on {HOST}:{PORT}, accounts at {AUTH_URL}\n")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
