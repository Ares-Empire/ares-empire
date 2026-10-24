#!/usr/bin/env python3
"""Empire push service: one process, two listeners (docs/PUSH.md).

  public    127.0.0.1:8095  POST/DELETE /api/push/devices   the apps, via Caddy (www.ares-empire.de/api/push/*)
  internal  127.0.0.1:8096  POST /send, GET /health          province services on this host; Caddy never routes here

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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from push.accounts import Accounts
from push.apns import Apns, HttpxTransport, ProviderToken
from push.config import HOST, APIError, Config
from push.service import PushService
from push.store import Store

log = logging.getLogger("push")

MAX_BODY_BYTES = 10_000
CLEAN_UP_EVERY = 24 * 60 * 60


class Handler(BaseHTTPRequestHandler):
    """JSON in, JSON out. `self.server.service` is the PushService; `routes` is set per listener below."""

    routes: dict[tuple[str, str], Callable[[Handler], None]] = {}
    server_version = "EmpirePush"
    sys_version = ""

    def log_message(self, fmt, *args):  # one short line per request, never a header or body
        log.info("%s - %s", self.address_string(), fmt % args)

    @property
    def service(self) -> PushService:
        return self.server.service

    def _dispatch(self) -> None:
        path = urlparse(self.path).path
        route = self.routes.get((self.command, path))
        try:
            if route is None:
                if any(path == known for _, known in self.routes):
                    raise APIError(405, "Method not allowed.")
                raise APIError(404, "Unknown route.")
            route(self)
        except APIError as e:
            self.send_json({"error": e.message}, e.status)
        except Exception:
            log.exception("%s %s failed", self.command, path)
            self.send_json({"error": "Internal error."}, 500)

    do_GET = do_POST = do_DELETE = do_PUT = do_PATCH = do_HEAD = _dispatch

    def bearer(self) -> str:
        match = re.fullmatch(r"Bearer\s+(\S+)", self.headers.get("Authorization", ""), re.I)
        return match[1] if match else ""

    def client_ip(self) -> str:
        # Caddy sets X-Forwarded-For to the visitor's address; the last entry is the one it added.
        forwarded = self.headers.get("X-Forwarded-For", "")
        return forwarded.split(",")[-1].strip() if forwarded else self.client_address[0]

    def json_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise APIError(400, "Invalid content length.")
        if length > MAX_BODY_BYTES:
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

    def send_json(self, data: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
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


class PublicHandler(Handler):
    routes = {("POST", "/api/push/devices"): register_device,
              ("DELETE", "/api/push/devices"): unregister_device}


class InternalHandler(Handler):
    routes = {("POST", "/send"): send,
              ("GET", "/health"): health}


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


def serve(handler: type[Handler], port: int, service: PushService) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((HOST, port), handler)
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
