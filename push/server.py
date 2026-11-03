#!/usr/bin/env python3
"""Empire push service: one process, two listeners (docs/PUSH.md).

  public    127.0.0.1:8095  POST/DELETE /api/push/devices   the apps, via Caddy (www.ares-empire.de/api/push/*)
  internal  127.0.0.1:8096  POST /send, GET /health,         province services and the account server on this host;
                            DELETE /internal/accounts/<id>[/devices[/arestemis]]   Caddy never routes here

Each listener only knows its own route table, so no path on the public port reaches /send.
Without the APNs key settings it runs as a dry run: messages are kept in the outbox, nothing is sent.

Run: python3 -m push.server (from the repo root, or /opt/empire-push on the server). Settings: push/.env.example.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import threading
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import unquote, urlparse

from empire_http import LimitedHTTPServer, LimitedRequestHandler
from empire_language import request_language
from push.accounts import Accounts
from push.apns import Apns, HttpxTransport, ProviderToken
from push.config import HOST, APIError, Config
from push.service import PushService
from push.store import Store
from push.texts import text

log = logging.getLogger("push")

MAX_REQUESTS = 16  # per listener; internal calls have their own slots
CLEAN_UP_EVERY = 24 * 60 * 60


def match(template: str, path: str) -> dict[str, str] | None:
    """The `{name}` parts of `path` when it has the template's shape ("/internal/accounts/{account}" matches
    "/internal/accounts/abc"), else None. A `{name}` part is one non-empty path segment."""
    want, got = template.split("/"), path.split("/")
    if len(want) != len(got):
        return None
    params = {}
    for part, value in zip(want, got):
        if part.startswith("{") and part.endswith("}"):
            if not value:
                return None
            params[part[1:-1]] = unquote(value)
        elif part != value:
            return None
    return params


class Handler(LimitedRequestHandler, BaseHTTPRequestHandler):
    """JSON in, JSON out. `self.server.service` is the PushService; `routes` is set per listener below (paths may
    have `{name}` parts, handed to the route as `self.params`)."""

    routes: dict[tuple[str, str], Callable[[Handler], None]] = {}
    params: dict[str, str] = {}
    server_version = "EmpirePush"
    sys_version = ""

    def log_message(self, fmt, *args):  # one short line per request, never a header or body
        log.info("%s - %s", self.address_string(), fmt % args)

    @property
    def service(self) -> PushService:
        return self.server.service

    def _dispatch(self) -> None:
        path = urlparse(self.path).path
        try:
            route, other_method = None, False
            for (method, template), handler in self.routes.items():
                params = match(template, path)
                if params is None:
                    continue
                if method != self.command:
                    other_method = True
                    continue
                route, self.params = handler, params
                break
            if route is None:
                raise APIError(405 if other_method else 404, "Method not allowed." if other_method else "Unknown route.")
            route(self)
        except APIError as e:
            self.send_json({"error": text(e.message, self.language)}, e.status)
        except Exception:
            log.exception("%s %s failed", self.command, path)
            self.send_json({"error": text("Internal error.", self.language)}, 500)

    do_GET = do_POST = do_DELETE = do_PUT = do_PATCH = do_HEAD = _dispatch

    @property
    def language(self) -> str:
        return request_language(self.headers.get("Accept-Language"))

    def bearer(self) -> str:
        match = re.fullmatch(r"Bearer\s+(\S+)", self.headers.get("Authorization", ""), re.I)
        return match[1] if match else ""

    def client_ip(self) -> str:
        return self.request_client_ip()

    def json_body(self) -> dict:
        if not self.request_body:
            raise APIError(400, "A JSON object is required.")
        try:
            body = json.loads(self.request_body)
        except (ValueError, UnicodeError):
            raise APIError(400, "Invalid JSON.")
        if not isinstance(body, dict):
            raise APIError(400, "A JSON object is required.")
        return body

    def request_error(self, status, message):
        self.send_json({"error": text(message, self.language)}, status)

    def send_json(self, data: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Language", self.language)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_no_content(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()


# ── Routes ───────────────────────────────────────────────────────────────────

def register_device(h: Handler) -> None:
    h.service.register(h.bearer(), h.client_ip(), h.json_body())
    h.send_no_content()


def unregister_device(h: Handler) -> None:
    h.service.unregister(h.bearer(), h.client_ip(), h.json_body())
    h.send_no_content()


def send(h: Handler) -> None:
    h.send_json(h.service.send(h.json_body()))


def health(h: Handler) -> None:
    h.send_json(h.service.health())


def delete_account(h: Handler) -> None:
    h.service.delete_account(h.params["account"])
    h.send_no_content()


def remove_devices(h: Handler) -> None:
    generations = h.headers.get_all("X-Empire-Access-Generation", [])
    if len(generations) != 1 or not re.fullmatch(r"[0-9]{1,16}", generations[0]):
        raise APIError(400, "Invalid access generation.")
    h.service.remove_devices(h.params["account"], h.params.get("app"), int(generations[0]))
    h.send_no_content()


class PublicHandler(Handler):
    routes = {("POST", "/api/push/devices"): register_device,
              ("DELETE", "/api/push/devices"): unregister_device}


class InternalHandler(Handler):
    routes = {("POST", "/send"): send,
              ("GET", "/health"): health,
              ("DELETE", "/internal/accounts/{account}"): delete_account,
              ("DELETE", "/internal/accounts/{account}/devices"): remove_devices,
              ("DELETE", "/internal/accounts/{account}/devices/{app}"): remove_devices}


# ── Running ──────────────────────────────────────────────────────────────────

def configure_logging() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    log.setLevel(logging.INFO)
    # httpx logs every request URL at INFO, and APNs URLs end in the device token.
    for name in ("httpx", "httpcore", "hpack", "h2"):
        logging.getLogger(name).setLevel(logging.WARNING)


def make_apns(config: Config) -> Apns | None:
    if config.dry_run:
        log.warning("DRY RUN: %s not set. Messages go to the outbox, nothing is sent to Apple.",
                    ", ".join(config.missing_key_settings))
        return None
    try:
        with open(config.key_file, "rb") as f:
            token = ProviderToken(f.read(), config.key_id, config.team_id)
    except (OSError, ValueError) as e:
        # A key that is set but unusable is a setup mistake: stop instead of quietly not sending.
        raise SystemExit(f"Cannot use the APNs key {config.key_file}: {e}")
    log.info("sending through APNs with key %s of team %s", config.key_id, config.team_id)
    return Apns(token, HttpxTransport())


def clean_up_daily(service: PushService, stop: threading.Event, every: float = CLEAN_UP_EVERY) -> None:
    while True:
        try:
            service.prune()
        except Exception:
            log.exception("daily clean-up failed")
        if stop.wait(every):
            return


def serve(handler: type[Handler], port: int, service: PushService) -> LimitedHTTPServer:
    client_options = {"max_per_client": 4, "rate": 1, "burst": 20}
    if handler is InternalHandler:
        client_options = {"max_per_client": None}
    httpd = LimitedHTTPServer((HOST, port), handler, max_requests=MAX_REQUESTS, **client_options)
    httpd.service = service
    return httpd


def main() -> None:
    configure_logging()
    config = Config.from_env()
    service = PushService(Store(config.db_path), Accounts(config.auth_url), make_apns(config))
    public = serve(PublicHandler, config.public_port, service)
    internal = serve(InternalHandler, config.internal_port, service)
    threading.Thread(target=public.serve_forever, name="public", daemon=True).start()
    threading.Thread(target=clean_up_daily, args=(service, threading.Event()), name="clean-up", daemon=True).start()
    log.info("public on %s:%d, internal on %s:%d, accounts at %s, data %s",
             HOST, config.public_port, HOST, config.internal_port, config.auth_url, config.db_path)
    internal.serve_forever()


if __name__ == "__main__":
    main()
