#!/usr/bin/env python3
"""Writes the Empire app's fixtures from the hub server itself: python3 tools/empire_samples.py OUTDIR

Every file is the hub's exact answer, made by webauth/server.py's own request handler in memory, with made-up accounts,
a fake account server and made-up live lines (no network, no real account data). The provinces, expansions and
chronicle are the committed seed, web/app/empire-data.js. The catalog and one install link are made up too (SAMPLE_CATALOG,
SAMPLE_INSTALL), so every state the apps show appears; the committed catalog opens no app yet. Contract:
docs/API-EMPIRE.md. The files go into the iPhone repo (empire-ios) by hand; run this again whenever the contract or the
seed changes.

  empire.admin.json        GET /api/empire as an admin: every province, the expansions, the whole chronicle, pending
  empire.member.json       the same as a member with one app (Arestemis, with an install link) and the "+" catalog
  empire.new-member.json   the same as a member approved just now: an empty ring and the catalog to ask from
  empire.requested.json    the same as a member who asked for Arestemis: in the "+", waiting for approval
  access-request.json      POST /api/empire/request {service: "arestemis"} as the new member: the fresh hub data
  approvals.json           GET /api/empire/approvals: two sign-ups (one email not confirmed) and a member asking for more
  approval-decision.json   POST /api/empire/approvals/<id> {approve: true, requested: <the card's apps>} on a sign-up
  error.<code>.json        one error answer per code clients act on

`--web` writes the hub website's own previews instead (WEB_PREVIEWS into web/app/samples, which the localhost preview
loads; tools/test_empire_samples.py checks they are current), and the public demo's two files (DEMO_FILE and
DEMO_WORDS_FILE, see "The public demo" below).

The check_* functions say whether an answer has the contract's shape (webauth/test_server.py uses them too).
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import re
import sys
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from webauth import server  # noqa: E402

SEED = REPO_ROOT / "web" / "app" / "empire-data.js"
WEB_SAMPLES = REPO_ROOT / "web" / "app" / "samples"
# The fixtures the website's localhost preview loads (web/app/empire-api.js: ?as=admin|member|new-member|requested).
WEB_PREVIEWS = ("empire.admin.json", "empire.member.json", "empire.new-member.json", "empire.requested.json",
                "approvals.json")


# ── The seed (plain JavaScript data) ─────────────────────────────────────────
# web/app/empire-data.js is the only copy of the seed and is JavaScript: comments, unquoted keys, strings joined with
# "+", trailing commas. This reads that subset of JavaScript; anything else (a template string, a function call) is an
# error naming the line, so a change to the seed's form shows up here instead of as a wrong fixture.

_TOKEN = re.compile(r"""
    (?P<space>\s+|//[^\n]*|/\*.*?\*/)
  | (?P<string>"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')
  | (?P<number>-?\d+(?:\.\d+)?)
  | (?P<name>[A-Za-z_$][\w$]*)
  | (?P<punct>[{}\[\]:,+;=()])
""", re.S | re.X)
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}


def _js_string(literal: str) -> str:
    body, out, i = literal[1:-1], [], 0
    while i < len(body):
        if body[i] != "\\":
            out.append(body[i])
            i += 1
        elif body[i + 1] == "u":
            out.append(chr(int(body[i + 2:i + 6], 16)))
            i += 6
        elif body[i + 1] == "x":
            out.append(chr(int(body[i + 2:i + 4], 16)))
            i += 4
        else:
            out.append(_ESCAPES.get(body[i + 1], body[i + 1]))
            i += 2
    return "".join(out)


class _Reader:
    """Reads one value from `start`, token by token, and stops after it (the rest of the file is code)."""

    def __init__(self, source: str, start: int):
        self.source, self.position = source, start

    def _token(self, advance: bool) -> tuple[str, str]:
        position = self.position
        while True:
            match = _TOKEN.match(self.source, position)
            if not match:
                if position >= len(self.source):
                    raise ValueError(f"{SEED.name}: ends in the middle of the data")
                raise self._fail("not plain data", position)
            position = match.end()
            if match.lastgroup != "space":
                break
        if advance:
            self.position = position
        return match.lastgroup, match.group()

    def _next(self) -> tuple[str, str]:
        return self._token(advance=True)

    def _peek(self) -> str:
        return self._token(advance=False)[1]

    def _fail(self, what: str, position: int | None = None) -> ValueError:
        line = self.source.count("\n", 0, self.position if position is None else position) + 1
        return ValueError(f"{SEED.name} line {line}: {what}")

    def value(self):
        kind, text = self._next()
        if kind == "string":
            joined = _js_string(text)
            while self._peek() == "+":
                self._next()
                kind, text = self._next()
                if kind != "string":
                    raise self._fail("only strings can be joined with +")
                joined += _js_string(text)
            return joined
        if kind == "number":
            return float(text) if "." in text else int(text)
        if kind == "name":
            # true/false/null, or a reference to a variable (STATUS), which the fixtures do not need
            return {"true": True, "false": False, "null": None}.get(text)
        if text == "{":
            return self._object()
        if text == "[":
            return self._array()
        raise self._fail(f"unexpected {text!r}")

    def _object(self) -> dict:
        result = {}
        while self._peek() != "}":
            kind, key = self._next()
            if kind not in ("name", "string"):
                raise self._fail(f"unexpected {key!r} where a key belongs")
            key = _js_string(key) if kind == "string" else key
            if self._peek() == ":":
                self._next()
                result[key] = self.value()
            else:
                result[key] = None  # shorthand property (`STATUS,`)
            if self._peek() == ",":
                self._next()
            elif self._peek() != "}":
                raise self._fail("expected , or }")
        self._next()
        return result

    def _array(self) -> list:
        result = []
        while self._peek() != "]":
            result.append(self.value())
            if self._peek() == ",":
                self._next()
            elif self._peek() != "]":
                raise self._fail("expected , or ]")
        self._next()
        return result


def read_seed_const(name: str, path: Path = SEED) -> dict:
    """One `const NAME = {...}` object of the seed: EMPIRE (words, projects, ideas, chronicle) or STATUS (the status
    words, which EMPIRE only names)."""
    source = path.read_text(encoding="utf-8")
    match = re.search(r"\bconst\s+" + re.escape(name) + r"\s*=\s*(?=\{)", source)
    if not match:
        raise ValueError(f"{path.name}: no `const {name} = {{` found")
    return _Reader(source, match.end()).value()


def read_seed_object(path: Path = SEED) -> dict:
    """The seed's whole EMPIRE object."""
    return read_seed_const("EMPIRE", path)


def read_seed(path: Path = SEED) -> dict:
    """The seed's {projects, ideas, chronicle}, as data/state.json holds them."""
    empire = read_seed_object(path)
    return {key: empire.get(key) for key in ("projects", "ideas", "chronicle")}


# ── The contract's shapes (docs/API-EMPIRE.md) ───────────────────────────────

def _check_fields(where: str, value: object, fields: dict, problems: list[str]) -> None:
    """`fields`: name → a predicate. The value must have exactly these fields, each passing its predicate."""
    if not isinstance(value, dict):
        problems.append(f"{where}: not an object")
        return
    if set(value) != set(fields):
        problems.append(f"{where}: fields {sorted(value)} instead of {sorted(fields)}")
    for name, ok in fields.items():
        if name in value and not ok(value[name]):
            problems.append(f"{where}.{name}: {value[name]!r} has the wrong type or value")


def _text(value) -> bool:
    return isinstance(value, str)


def _texts(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _optional_text(value) -> bool:
    return value is None or isinstance(value, str)


def _count(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _flag(value) -> bool:
    return isinstance(value, bool)


def _list_of(where: str, value: object, check, problems: list[str]) -> None:
    if not isinstance(value, list):
        problems.append(f"{where}: not a list")
        return
    for number, item in enumerate(value):
        check(f"{where}[{number}]", item, problems)


def _province(where: str, value: object, problems: list[str]) -> None:
    _check_fields(where, value, {
        "slug": lambda v: isinstance(v, str) and bool(server.SLUG.fullmatch(v)), "name": _text, "url": _text,
        "logo": _text, "status": _text, "domain": _text, "blurb": _text, "detail": lambda v: True,
        "state": lambda v: v in ("open", "coming-soon"), "live": _optional_text, "app": _optional_text,
        "install": lambda v: v is None or (isinstance(v, str) and v.startswith("https://")),
        "access": lambda v: v in ("granted", "requested", "none"),
    }, problems)
    if isinstance(value, dict):
        _check_fields(where + ".detail", value.get("detail"), {
            "about": _text, "features": _texts, "setup": _text, "wip": _texts, "ideas": _texts,
            "changelog": lambda v: isinstance(v, list) and all(
                isinstance(e, dict) and set(e) == {"at", "text"} and _text(e["at"]) and _text(e["text"]) for e in v),
        }, problems)


def _chronicle_entry(where: str, value: object, problems: list[str]) -> None:
    _check_fields(where, value, {"at": _text, "project": _optional_text, "text": _text}, problems)


def _idea(where: str, value: object, problems: list[str]) -> None:
    _check_fields(where, value, {"title": _text, "note": _text}, problems)


def check_empire(data: object) -> list[str]:
    """What keeps a GET /api/empire answer from the contract (empty when it matches)."""
    problems: list[str] = []
    _check_fields("empire", data, {
        "version": lambda v: v == 2, "me": lambda v: True, "projects": lambda v: True, "addable": lambda v: True,
        "chronicle": lambda v: True, "ideas": lambda v: True, "pending": lambda v: v is None or _count(v),
    }, problems)
    if not isinstance(data, dict):
        return problems
    _check_fields("empire.me", data.get("me"), {"id": _text, "name": _text, "admin": _flag}, problems)
    _list_of("empire.projects", data.get("projects"), _province, problems)
    _list_of("empire.addable", data.get("addable"), _province, problems)
    _list_of("empire.chronicle", data.get("chronicle"), _chronicle_entry, problems)
    _list_of("empire.ideas", data.get("ideas"), _idea, problems)
    for key in ("projects", "addable"):
        slugs = [p.get("slug") for p in data.get(key) or [] if isinstance(p, dict)]
        if len(slugs) != len(set(slugs)):
            problems.append(f"empire.{key}: a slug appears twice")
    if isinstance(data.get("me"), dict) and data["me"].get("admin") is False:
        if data.get("pending") != 0 or data.get("ideas") != []:
            problems.append("empire: a member gets pending 0 and no ideas")
    elif isinstance(data.get("me"), dict) and data["me"].get("admin") is True and data.get("addable") != []:
        problems.append("empire: an admin has every province, so nothing in addable")
    # The ring is what the account has; the "+" what it may ask for. Install links only for apps the account has.
    for number, province in enumerate(p for p in data.get("projects") or [] if isinstance(p, dict)):
        if (province.get("state"), province.get("access")) != ("open", "granted"):
            problems.append(f"empire.projects[{number}]: a ring province is open and granted")
    for number, province in enumerate(p for p in data.get("addable") or [] if isinstance(p, dict)):
        if province.get("access") not in ("requested", "none") or province.get("install") is not None:
            problems.append(f"empire.addable[{number}]: requested or none, and never an install link")
        if province.get("access") == "requested" and province.get("state") != "open":
            problems.append(f"empire.addable[{number}]: only an open app can be requested")
    return problems


def _approval(where: str, value: object, problems: list[str]) -> None:
    _check_fields(where, value, {"id": _text, "email": _text, "name": _text, "created": _text,
                                 "requested": _texts, "approved": _flag, "verified": _flag}, problems)


def check_approvals(data: object) -> list[str]:
    """What keeps a GET /api/empire/approvals answer from the contract."""
    problems: list[str] = []
    _list_of("approvals", data, _approval, problems)
    return problems


def check_decision(data: object) -> list[str]:
    """What keeps a POST /api/empire/approvals/<id> answer from the contract."""
    problems: list[str] = []
    _check_fields("decision", data, {"ok": lambda v: v is True, "approvals": lambda v: True,
                                     "pending": lambda v: v is None or _count(v)}, problems)
    if isinstance(data, dict):
        if data.get("approvals") is None:
            if data.get("pending") is not None:
                problems.append("decision: pending without approvals")
        else:
            problems += check_approvals(data.get("approvals"))
            if isinstance(data.get("approvals"), list) and data.get("pending") != len(data["approvals"]):
                problems.append("decision: pending is not the number of approvals")
    return problems


def check_error(data: object) -> list[str]:
    """What keeps an error answer from the contract: {error: a sentence, code: one of the codes}."""
    problems: list[str] = []
    _check_fields("error", data, {"error": lambda v: isinstance(v, str) and bool(v.strip()),
                                  "code": lambda v: v in server.ERROR_CODES}, problems)
    return problems


# ── A made-up world: accounts, a fake account server, live lines ─────────────

CREATED = "2026-10-24 08:40:00.000Z"  # PocketBase's date format
ACCOUNTS = {  # token → the account record auth-refresh returns
    "sample-admin-token": {"id": "sampleadmin0001", "name": "Commander", "admin": True, "approved": True,
                           "verified": True, "services": ["empire", "aresium", "aresus"], "requested": []},
    "sample-member-token": {"id": "samplemember001", "name": "Robin Vale", "admin": False, "approved": True,
                            "verified": True, "services": ["empire", "arestemis"], "requested": []},
    "sample-new-member-token": {"id": "samplenewmbr001", "name": "", "admin": False, "approved": True,
                                "verified": True, "services": ["empire"], "requested": []},
    "sample-requested-token": {"id": "samplerequest01", "name": "Sam Okafor", "admin": False, "approved": True,
                               "verified": True, "services": ["empire"], "requested": ["arestemis"]},
    "sample-no-access-token": {"id": "samplenoacce001", "name": "Kim", "admin": False, "approved": True,
                               "verified": True, "services": ["arestemis"], "requested": []},
}
# Which apps other accounts may ask for: Arestemis open, Aresium coming soon (the committed catalog opens nothing yet).
SAMPLE_CATALOG = {"aresium": {"users": "coming-soon"}, "arestemis": {"users": "open"}}
# A made-up install link for Arestemis (apps.json has none until there is a TestFlight link).
SAMPLE_INSTALL = {"arestemis": "https://example.com/testflight/arestemis"}
WAITING = [  # accounts waiting for Patrik (fictional example.com addresses)
    {"id": "samplesignup001", "email": "alex@example.com", "name": "Alex Rowan", "created": CREATED,
     "approved": False, "verified": True, "services": [], "requested": ["empire", "arestemis"]},
    {"id": "samplesignup002", "email": "jo@example.com", "name": "", "created": "2026-10-25 07:12:00.000Z",
     "approved": False, "verified": False, "services": [], "requested": ["aresium"]},
    {"id": "sampleasking001", "email": "robin@example.com", "name": "Robin Vale", "created": "2026-10-20 18:05:00.000Z",
     "approved": True, "verified": True, "services": ["empire"], "requested": ["aresium", "aresus"]},
]
# Made-up live lines; only the admin gets them (Aresium and Aresus let only their owner in).
PULSE = {"line": "€1,339 spent in October"}
ARESUS = {"provinces": [
    {"slug": "arestoteles", "state": "active", "line": "Website up · vault synced 2 min ago"},
    {"slug": "arestemis", "state": "issue", "line": "Server down since 04:53"},
    {"slug": "aresync", "state": "active", "line": "Last sync 3 min ago on 2 machines"},
    {"slug": "aresus", "state": "active", "line": "All running · checked 1 min ago"},
]}


class FakeAccountServer:
    """The few PocketBase calls the hub makes, over the records above; approve, decline and an account's own request
    apply the account server's two rules (accounts.pb.js → settle)."""

    def __init__(self):
        self.waiting = copy.deepcopy(WAITING)
        self.accounts = copy.deepcopy(ACCOUNTS)

    def __call__(self, path, body=None, token=None, client_ip=None, method="POST"):
        me = self.accounts.get(token)
        if path.endswith("/auth-refresh"):
            return (200, {"record": copy.deepcopy(me)}) if me else (401, {})
        if me and path.partition("?")[0].endswith("/records/" + me["id"]):
            # An account reads its own record and asks for an app ("requested+"), as the hub's "+" does.
            if method == "PATCH":
                me["requested"] += [s for s in body["requested+"] if s not in me["requested"]]
                me["requested"] = [s for s in me["requested"] if s not in me["services"]]
                return 200, copy.deepcopy(me)
            return 200, {k: copy.deepcopy(me[k]) for k in ("id", "services", "requested")}
        if (me or {}).get("admin") is not True:
            return 403, {}
        if path.startswith("/api/collections/users/records?"):
            query = parse_qs(urlparse(path).query)
            if query["sort"] != ["created,id"]:
                raise ValueError("the fake account server sorts by created,id only")
            fields = query["fields"][0].split(",")
            items = [{k: account[k] for k in fields}
                     for account in sorted(self.waiting, key=lambda a: (a["created"], a["id"]))]
            return 200, {"items": items, "totalItems": len(items), "totalPages": 1}
        account_id = path.partition("?")[0].rsplit("/", 1)[1]
        account = next((a for a in self.waiting if a["id"] == account_id), None)
        if account is None:
            return 404, {}
        if method == "GET":
            return 200, {k: account[k] for k in ("id", "approved", "requested")}
        if method == "DELETE":
            self.waiting.remove(account)
            return 204, {}
        was_approved = account["approved"]
        account["approved"] = body.get("approved", account["approved"])
        account["services"] += [s for s in body.get("services+", []) if s not in account["services"]]
        account["requested"] = [s for s in account["requested"] if s not in body.get("requested-", [])]
        if account["approved"] and not was_approved:
            account["services"] += [s for s in account["requested"] if s not in account["services"]]
        account["requested"] = [s for s in account["requested"] if s not in account["services"]]
        if account["approved"] and not account["requested"]:
            self.waiting.remove(account)
        return 200, {"id": account_id}


def _live(url, token, language):
    if ACCOUNTS.get(token, {}).get("admin") is not True:
        return None  # the provinces answer 403 to everyone but their owner
    return copy.deepcopy(ARESUS if url == server.ARESUS_OVERVIEW_URL else PULSE)


_load_committed_apps = server.load_apps  # fake_world() replaces server.load_apps with _apps


def _apps():
    """The committed apps.json with the made-up install link."""
    apps = _load_committed_apps()
    for slug, link in SAMPLE_INSTALL.items():
        apps[slug] = {**apps.get(slug, {"scheme": None}), "install": link}
    return apps


@contextlib.contextmanager
def fake_world(seed: dict | None = None):
    """The hub server with the seed as its state.json, the fake account server and the made-up live lines."""
    state = seed if seed is not None else read_seed()
    with contextlib.ExitStack() as stack:
        server._cache.clear()
        server._live_cache.clear()
        stack.callback(server._cache.clear)
        stack.callback(server._live_cache.clear)
        stack.enter_context(patch.object(server, "pb_call", FakeAccountServer()))
        stack.enter_context(patch.object(server, "read_state", lambda: copy.deepcopy(state)))
        stack.enter_context(patch.object(server, "load_catalog", lambda: copy.deepcopy(SAMPLE_CATALOG)))
        stack.enter_context(patch.object(server, "load_apps", _apps))
        stack.enter_context(patch.object(server, "_fetch_json", _live))
        stack.enter_context(patch.object(server, "log", lambda message: None))
        stack.enter_context(patch.object(server.Handler, "log_message", lambda *args: None))
        yield


class _Socket:
    def __init__(self, request: bytes):
        self.input, self.output = io.BytesIO(request), io.BytesIO()

    def makefile(self, *args):
        return self.input

    def sendall(self, data: bytes):
        self.output.write(data)


def answer(method: str, path: str, token: str | None = None, body: object = None,
           language: str = "en") -> tuple[int, object]:
    """One request through the hub's own handler, in memory: (status, the JSON answer)."""
    payload = json.dumps(body).encode() if body is not None else b""
    headers = {"Host": "www.ares-empire.de", "Accept-Language": language}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    if payload:
        headers.update({"Content-Type": "application/json", "Content-Length": str(len(payload))})
    head = f"{method} {path} HTTP/1.0\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    sock = _Socket(head.encode() + b"\r\n" + payload)
    server.Handler(sock, ("127.0.0.1", 1234), object())
    response_head, response_body = sock.output.getvalue().split(b"\r\n\r\n", 1)
    return int(response_head.split(b" ", 2)[1]), json.loads(response_body)


def _expect(name: str, result: tuple[int, object], status: int, check) -> object:
    got, data = result
    problems = ([f"status {got} instead of {status}"] if got != status else []) + check(data)
    if problems:
        raise ValueError(f"{name}: " + "; ".join(problems))
    return data


def build(seed: dict | None = None) -> dict[str, object]:
    """Every fixture, by file name, checked against the contract."""
    samples: dict[str, object] = {}
    with fake_world(seed):
        admin, member, new_member = "sample-admin-token", "sample-member-token", "sample-new-member-token"
        samples["empire.admin.json"] = _expect("admin", answer("GET", "/api/empire", admin), 200, check_empire)
        samples["empire.member.json"] = _expect("member", answer("GET", "/api/empire", member), 200, check_empire)
        samples["empire.new-member.json"] = _expect("new member", answer("GET", "/api/empire", new_member), 200,
                                                    check_empire)
        samples["empire.requested.json"] = _expect("requested", answer(
            "GET", "/api/empire", "sample-requested-token"), 200, check_empire)
        samples["access-request.json"] = _expect("access request", answer(
            "POST", "/api/empire/request", new_member, {"service": "arestemis"}), 200, check_empire)
        approvals = _expect("approvals", answer("GET", "/api/empire/approvals", admin), 200, check_approvals)
        samples["approvals.json"] = approvals
        card = next(a for a in approvals if not a["approved"])  # a sign-up; the app sends the apps its card showed
        samples["approval-decision.json"] = _expect("decision", answer(
            "POST", "/api/empire/approvals/" + card["id"], admin, {"approve": True, "requested": card["requested"]}),
            200, check_decision)

        errors = {
            "unauthorized": (401, answer("GET", "/api/empire", "sample-expired-token")),
            "no_access": (403, answer("GET", "/api/empire", "sample-no-access-token")),
            "admin_only": (403, answer("GET", "/api/empire/approvals", member)),
            "bad_request": (400, answer("POST", "/api/empire/request", member, {"service": "aresium"})),
            "not_found": (404, answer("POST", "/api/empire/approvals/samplemissing01", admin, {"decline": True})),
        }
        with patch.object(server, "read_state", side_effect=server.APIError(503, "Hub data unavailable, try again "
                                                                                  "in a minute.")):
            errors["unavailable"] = (503, answer("GET", "/api/empire", admin))
        with patch.object(server, "load_catalog", side_effect=RuntimeError("made-up failure")):
            errors["server_error"] = (500, answer("GET", "/api/empire", admin))
        for code, (status, result) in errors.items():
            data = _expect("error " + code, result, status, check_error)
            if data["code"] != code:
                raise ValueError(f"error {code}: the server answered code {data['code']}")
            samples[f"error.{code}.json"] = data
    return samples


# ── The public demo (www.ares-empire.de/demo) ─────────────────────────────────
# The hub for anyone, without an account (webauth/server.py serves it; web/app/empire-api.js loads these two files on
# /demo). A made-up guest has the apps on the ring, with texts written for strangers and a made-up chronicle: when each
# was started and finished (Patrik, 2026-10-27). Aresium links its own demo, Arestemis and Arestoteles the request form;
# Aresus and Aresync, Patrik's own tools, are shown without a link or an install button. Nothing of the real seed's
# content goes into it: only its words (name, tagline, STATUS) and the provinces' logos.
DEMO_FILE = "empire.demo.json"
DEMO_WORDS_FILE = "demo-empire.js"          # window.EMPIRE on the demo page, in place of app/empire-data.js
DEMO_TOKEN = "sample-demo-token"
DEMO_REQUEST = "https://www.ares-empire.de/contact"   # where a guest asks for an app (the contact form for now)
ACCOUNTS[DEMO_TOKEN] = {"id": "sampledemo00001", "name": "Guest", "admin": False, "approved": True, "verified": True,
                        "services": ["empire", "aresium", "arestemis", "arestoteles", "aresus", "aresync"],
                        "requested": []}
DEMO_PROVINCES = {   # slug → what the demo says about it; the ring keeps this order
    "aresium": {
        "url": "https://aresium.de/demo", "domain": "aresium.de", "blurb": "Personal finance, understood.",
        "about": "Aresium reads bank and PayPal exports, sorts every transaction into categories and shows where the "
                 "money goes, month by month.",
        "features": ["Automatic categories", "Clear charts by month and category", "Image processing for receipts"]},
    "arestemis": {
        "url": DEMO_REQUEST, "domain": "", "blurb": "Flat finding on autopilot.",
        "about": "Arestemis keeps one search for the flat you want, has an AI check every new listing against it and "
                 "tells you the moment a match goes live.",
        "features": ["One search: places, size, rent, move-in date", "An AI check of every new listing",
                     "Instant alerts for matching listings"]},
    "arestoteles": {
        "url": DEMO_REQUEST, "domain": "", "blurb": "A personal wiki, on every device.",
        "about": "Arestoteles keeps detailed notes and fact-based positions, each with the evidence behind it, "
                 "searchable by meaning on every device.",
        "features": ["Positions with the evidence behind them", "RAG search across all notes",
                     "Edits synced across devices"]},
    "aresus": {
        "url": "", "domain": "", "blurb": "Digital infrastructure at a glance.", "install": False,
        "about": "Aresus checks every app and service around the clock, shows the sync status of every machine and "
                 "sends an alert the moment something breaks.",
        "features": ["Every app and service checked around the clock", "Sync status of every machine",
                     "An alert the moment something breaks"]},
    "aresync": {
        "url": "", "domain": "", "blurb": "Every repository on every machine, in sync.", "install": False,
        "about": "Aresync keeps every Git repository in step across laptops and the server: it commits, rebases and "
                 "pushes on its own and reports each run to Aresus.",
        "features": ["Commit, rebase and push on its own", "Every repository on every machine",
                     "Each run reported to Aresus"]},
}
DEMO_CHRONICLE = [   # newest first, as the hub shows it
    {"at": "2026-10-25", "project": "aresus", "text": "Aresus is finished: every app and service watched, with an alert "
                                                      "the moment something breaks."},
    {"at": "2026-10-24", "project": "aresium", "text": "Aresium's iPhone app is finished: categories, charts and "
                                                       "receipts, right on the phone."},
    {"at": "2026-10-21", "project": "arestoteles", "text": "Arestoteles is finished: positions, evidence and RAG "
                                                           "search on every device."},
    {"at": "2026-10-18", "project": "arestemis", "text": "Arestemis is finished: an instant alert for every matching "
                                                         "listing."},
    {"at": "2026-10-02", "project": "aresync", "text": "Aresync is finished: every repository in step on every machine, "
                                                       "each run reported to Aresus."},
    {"at": "2026-09-30", "project": "arestoteles", "text": "Arestoteles started: a personal wiki for positions and the "
                                                           "evidence behind them."},
    {"at": "2026-09-12", "project": "arestemis", "text": "Arestemis started: a flat finder that checks every new "
                                                         "listing against one search."},
    {"at": "2026-09-05", "project": "aresus", "text": "Aresus started: a watchtower for the empire's apps, services and "
                                                      "machines."},
    {"at": "2026-08-28", "project": "aresium", "text": "Aresium joined the empire: personal finance, from bank exports "
                                                       "to clear charts."},
    {"at": "2026-08-14", "project": "aresync", "text": "Aresync started: one sync for every repository on every "
                                                       "machine."},
]


def demo_seed() -> dict:
    """The demo's state.json: the three provinces with the demo's texts, no expansions, the demo's chronicle."""
    seed = {p["slug"]: p for p in read_seed()["projects"]}
    projects = []
    for slug, says in DEMO_PROVINCES.items():
        projects.append({**seed[slug], "url": says["url"], "domain": says["domain"], "status": "CONQUERED",
                         "blurb": says["blurb"], "detail": {"about": says["about"], "features": says["features"],
                                                            "setup": "", "wip": [], "ideas": [], "changelog": []}})
    return {"projects": projects, "ideas": [], "chronicle": copy.deepcopy(DEMO_CHRONICLE)}


def _demo_apps():
    """The committed apps.json, with the guest's way to get each app (the request form; none for Patrik's own tools)."""
    apps = _load_committed_apps()
    return {slug: {**apps.get(slug, {"scheme": None}), "install": DEMO_REQUEST if says.get("install", True) else None}
            for slug, says in DEMO_PROVINCES.items()}


def build_demo() -> object:
    """The hub's answer to the demo guest, checked against the contract."""
    with fake_world(demo_seed()):
        with patch.object(server, "load_catalog", lambda: {slug: {"users": "open"} for slug in DEMO_PROVINCES}), \
                patch.object(server, "load_apps", _demo_apps):
            data = _expect("demo", answer("GET", "/api/empire", DEMO_TOKEN), 200, check_empire)
    if [p["slug"] for p in data["projects"]] != list(DEMO_PROVINCES) or data["addable"] or data["ideas"]:
        raise ValueError("demo: the guest must have exactly the demo's apps, nothing to ask for and no expansions")
    return data


def demo_words() -> str:
    """The demo page's window.EMPIRE: the seed's words only (name, tagline, STATUS), no provinces or chronicle."""
    empire = read_seed_object()
    words = {"name": empire["name"], "tagline": empire["tagline"], "STATUS": read_seed_const("STATUS")}
    return ("// Made by tools/empire_samples.py --web: the hub's words for the public demo (/demo), in place of\n"
            "// app/empire-data.js, which holds the real provinces and chronicle and stays behind the login.\n"
            "window.EMPIRE = " + json.dumps(words, indent=2, ensure_ascii=False) + ";\n")


def dump(data: object) -> str:
    """A fixture file's text."""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the Empire app's fixtures from the hub server itself.")
    parser.add_argument("outdir", type=Path, nargs="?", help="folder for the JSON files (created if missing)")
    parser.add_argument("--web", action="store_true", help=f"write the website's previews into {WEB_SAMPLES}")
    args = parser.parse_args(argv)
    if args.web == bool(args.outdir):
        parser.error("give either OUTDIR or --web")
    samples = build()
    if args.web:
        samples = {name: samples[name] for name in WEB_PREVIEWS}
        samples[DEMO_FILE] = build_demo()
    outdir = WEB_SAMPLES if args.web else args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    for name, data in samples.items():
        (outdir / name).write_text(dump(data), encoding="utf-8")
    if args.web:
        (outdir / DEMO_WORDS_FILE).write_text(demo_words(), encoding="utf-8")
    print(f"wrote {len(samples)} fixtures to {outdir}" + (f" and {DEMO_WORDS_FILE}" if args.web else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
