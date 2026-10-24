"""What the push service does, independent of HTTP: register and remove devices (public API, for the apps) and send
a message to devices (internal API, for the province services). Contract: docs/PUSH.md."""

from __future__ import annotations

import logging
import re
from dataclasses import replace

from push.accounts import Accounts, may_use
from push.apns import INTERRUPTIONS, MAX_PAYLOAD, Apns, Message
from push.config import APPS, APIError, short
from push.store import STALE_DAYS, Store

log = logging.getLogger("push")

DEVICE_TOKEN = re.compile(r"[0-9a-f]{64,200}")
ENVIRONMENTS = ("sandbox", "production")
USER_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
MESSAGE_TEXTS = ("title", "subtitle", "body", "url", "thread", "category", "collapse_id")
SEND_FIELDS = frozenset({"app", "to", "interruption", "sound", "localized", *MESSAGE_TEXTS})
LOCALIZED_FIELDS = frozenset({"title", "subtitle", "body"})


def parse_app(body: dict) -> str:
    app = body.get("app")
    if not isinstance(app, str) or app not in APPS:
        raise APIError(400, "Unknown app.")
    return app


def parse_device(body: dict, with_environment: bool) -> tuple[str, str, str]:
    """(app, device token, environment) of a devices request; environment is "" when not asked for."""
    app = parse_app(body)
    token = body.get("token")
    if not isinstance(token, str) or not DEVICE_TOKEN.fullmatch(token):
        raise APIError(400, "token must be the APNs device token as lowercase hex.")
    environment = ""
    if with_environment:
        environment = body.get("environment")
        if environment not in ENVIRONMENTS:
            raise APIError(400, 'environment must be "sandbox" or "production".')
    return app, token, environment


def parse_send(body: dict) -> tuple[dict[str, Message], str | None]:
    """The English/German messages and their account (None = every device of the app)."""
    # Strict on purpose: the senders are our own services, and a misspelt field (say "collapse") would otherwise
    # silently go missing on the phone.
    unknown = sorted(set(body) - SEND_FIELDS)
    if unknown:
        raise APIError(400, "Unknown field(s): " + ", ".join(unknown) + ".")
    app = parse_app(body)
    to = body.get("to")
    if isinstance(to, dict) and set(to) == {"all"} and to["all"] is True:
        user = None
    elif isinstance(to, dict) and set(to) == {"user"} and isinstance(to["user"], str) and USER_ID.fullmatch(to["user"]):
        user = to["user"]
    else:
        raise APIError(400, 'to must be {"user": "<account id>"} or {"all": true}.')
    texts = {}
    for field in MESSAGE_TEXTS:
        value = body.get(field, "")
        if not isinstance(value, str):
            raise APIError(400, f"{field} must be a string.")
        texts[field] = value
    if not texts["title"] and not texts["body"]:
        raise APIError(400, "A notification needs a title or a body.")
    if len(texts["collapse_id"].encode()) > 64:
        raise APIError(400, "collapse_id may have at most 64 bytes.")
    interruption = body.get("interruption", "active")
    if interruption not in INTERRUPTIONS:
        raise APIError(400, "interruption must be passive, active or time-sensitive.")
    sound = body.get("sound", False)
    if not isinstance(sound, bool):
        raise APIError(400, "sound must be true or false.")
    localized = body.get("localized", {})
    if not isinstance(localized, dict) or set(localized) - {"de"}:
        raise APIError(400, 'localized must be an object containing only "de".')
    german = localized.get("de", {})
    if not isinstance(german, dict) or set(german) - LOCALIZED_FIELDS:
        raise APIError(400, "localized.de may contain only title, subtitle and body.")
    if any(not isinstance(value, str) for value in german.values()):
        raise APIError(400, "localized.de fields must be strings.")
    english = Message(app=app, interruption=interruption, sound=sound, **texts)
    messages = {"en": english, "de": replace(english, **german)}
    for message in messages.values():
        if not message.title and not message.body:
            raise APIError(400, "A notification needs a title or a body.")
        if len(message.payload()) > MAX_PAYLOAD:
            raise APIError(400, "The notification is larger than Apple's 4 KB limit.")
    return messages, user


class PushService:
    def __init__(self, store: Store, accounts: Accounts, apns: Apns | None):
        """`apns` None = dry run: messages go to the outbox only."""
        self.store = store
        self.accounts = accounts
        self.apns = apns

    @property
    def dry_run(self) -> bool:
        return self.apns is None

    # Public API (the apps, with their Empire token)

    def register(self, empire_token: str, client_ip: str | None, body: dict) -> None:
        if not empire_token:
            raise APIError(401, "unauthenticated")
        app, token, environment = parse_device(body, with_environment=True)
        language = body.get("language", "en")
        if language not in ("en", "de"):
            raise APIError(400, 'language must be "en" or "de".')
        record = self.accounts.account(empire_token, client_ip)
        if not may_use(record, APPS[app]):
            raise APIError(403, "This account has no access to this app.")
        moved = self.store.register(app, token, record["id"], environment, language)
        log.info("registered %s device %s (%s)%s", app, short(token), environment,
                 ", moved from another account" if moved else "")

    def unregister(self, empire_token: str, client_ip: str | None, body: dict) -> None:
        """Any valid login may remove its own device, also one that lost the app's service (docs/PUSH.md)."""
        if not empire_token:
            raise APIError(401, "unauthenticated")
        app, token, _ = parse_device(body, with_environment=False)
        record = self.accounts.account(empire_token, client_ip)
        if self.store.unregister(app, token, record["id"]):
            log.info("removed %s device %s", app, short(token))

    # Internal API (province services on this host)

    def send(self, body: dict) -> dict:
        messages, user = parse_send(body)
        app = messages["en"].app
        devices = self.store.devices(app, user)
        results: dict[str, dict] = {}
        payloads = {language: message.payload() for language, message in messages.items()}
        for device in devices:
            language = device.language
            message = messages[language]
            result = results.setdefault(language, {"sent": 0, "failed": 0, "dry_run": self.dry_run, "removed": 0})
            if self.apns is None:
                result["sent"] += 1  # the devices it would have reached
            else:
                payload = payloads[language]
                outcome = self.apns.send(device.token, device.environment, message, payload)
                if outcome.status == "sent":
                    result["sent"] += 1
                    continue
                result["failed"] += 1
                if outcome.status == "stale":
                    self.store.remove(device.app, device.token)
                    result["removed"] += 1
                log.warning("%s device %s: %s (%s)%s", message.app, short(device.token), outcome.status,
                            outcome.reason, ", removed" if outcome.status == "stale" else "")
        answer = {"sent": sum(r["sent"] for r in results.values()),
                  "failed": sum(r["failed"] for r in results.values()), "dry_run": self.dry_run}
        # Retain the existing outbox entry for sends with no recipients as well.
        if not results:
            results["en"] = {**answer, "removed": 0}
        for language, result in results.items():
            message = messages[language]
            self.store.log(app, user or "all", message.title, message.body, message.url, result, language)
        log.info("%s %s to %s: %d sent, %d failed", "dry run" if self.dry_run else "sent", app,
                 "all" if user is None else "one account", answer["sent"], answer["failed"])
        return answer

    def health(self) -> dict:
        return {"ok": True, "dry_run": self.dry_run, "devices": self.store.counts()}

    def prune(self) -> int:
        removed = self.store.prune()
        if removed:
            log.info("dropped %d device(s) not re-registered for %d days", removed, STALE_DAYS)
        return removed
