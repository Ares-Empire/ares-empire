"""Push service contract tests: in-memory HTTP requests, fake PocketBase, fake Apple, no network.

Run from the repo root with the push venv: python3 -m unittest push/test_push.py
"""
import base64
import copy
import io
import json
import logging
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from push import accounts, apns, server, service, store
from push.config import APPS, HOST, Config

APP = "de.ares-empire.arestemis"
# Made-up device tokens (lowercase hex, as the apps send them).
DEVICE_A, DEVICE_B, DEVICE_C, DEVICE_D, DEVICE_E, DEVICE_F = (c * 64 for c in "abcdef")
DEVICES = (DEVICE_A, DEVICE_B, DEVICE_C, DEVICE_D, DEVICE_E, DEVICE_F)
START = 1_792_800_000.0  # 2026-10-24
DAY = 24 * 60 * 60


def pem(key) -> bytes:
    """A private key the way Apple's .p8 file holds it (PKCS#8 PEM)."""
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())


TEST_KEY = ec.generate_private_key(ec.SECP256R1())


class Clock:
    def __init__(self):
        self.now = START

    def __call__(self):
        return self.now


class Socket:
    def __init__(self, request):
        self.input = io.BytesIO(request)
        self.output = io.BytesIO()

    def makefile(self, *args):
        return self.input

    def sendall(self, body):
        self.output.write(body)


class FakeServer:
    def __init__(self, push_service):
        self.service = push_service


class FakeApple:
    """Records each APNs request; answers 200 unless `answers` holds (status, reason) for a device token."""

    def __init__(self):
        self.requests = []
        self.answers = {}

    def post(self, url, headers, body):
        self.requests.append({"url": url, "headers": headers, "payload": json.loads(body)})
        answer = self.answers.get(url.rsplit("/", 1)[1], (200, ""))
        if isinstance(answer, list):
            answer = answer.pop(0) if len(answer) > 1 else answer[0]
        status, reason = answer
        return status, json.dumps({"reason": reason}).encode() if reason else b""


class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


class PushTestCase(unittest.TestCase):
    dry_run = False

    def setUp(self):
        self.clock = Clock()
        self.store = store.Store(":memory:", clock=self.clock)
        self.addCleanup(self.store.close)
        self.records = {
            "member-one": {"id": "memberone000001", "approved": True, "services": ["empire", "arestemis"]},
            "member-two": {"id": "membertwo000002", "approved": True, "services": ["arestemis"]},
            "empire-only": {"id": "empireonly00003", "approved": True, "services": ["empire"]},
        }
        self.pb_calls = []
        self.accounts = accounts.Accounts("http://accounts.invalid", clock=self.clock)
        self.enterContext(patch.object(self.accounts, "refresh", side_effect=self.pocketbase))
        self.apple = FakeApple()
        self.provider = apns.ProviderToken(pem(TEST_KEY), "KEYID12345", "TEAMID1234", clock=self.clock)
        sender = None if self.dry_run else apns.Apns(self.provider, self.apple, clock=self.clock)
        self.service = service.PushService(self.store, self.accounts, sender)
        logger = logging.getLogger("push")
        self.logs = ListHandler()
        saved = logger.propagate, logger.level
        logger.addHandler(self.logs)
        logger.propagate, logger.level = False, logging.DEBUG
        self.addCleanup(lambda: (logger.removeHandler(self.logs), setattr(logger, "propagate", saved[0]),
                                 logger.setLevel(saved[1])))
        self.addCleanup(self.assert_no_full_tokens_logged)

    def assert_no_full_tokens_logged(self):
        text = "\n".join(self.logs.lines)
        for secret in (*DEVICES, *self.records):
            self.assertNotIn(secret, text)

    def pocketbase(self, token, client_ip=None):
        self.pb_calls.append((token, client_ip))
        if token not in self.records:
            return 400, {}
        return 200, {"record": copy.deepcopy(self.records[token])}

    def request(self, path="/api/push/devices", method="POST", body=None, token="member-one", handler=None,
                headers=None, raw=None):
        internal = path in ("/send", "/health") or path.startswith("/internal/")
        handler = handler or (server.InternalHandler if internal else server.PublicHandler)
        request_headers = {"Host": "push.example.com", "X-Forwarded-For": "192.0.2.5, 192.0.2.10"}
        if token is not None:
            request_headers["Authorization"] = "Bearer " + token
        if headers:
            request_headers.update(headers)
        payload = raw if raw is not None else (json.dumps(body).encode() if body is not None else b"")
        if payload:
            request_headers.setdefault("Content-Length", str(len(payload)))
            request_headers.setdefault("Content-Type", "application/json")
        head = f"{method} {path} HTTP/1.0\r\n" + "".join(f"{k}: {v}\r\n" for k, v in request_headers.items())
        sock = Socket(head.encode() + b"\r\n" + payload)
        handler(sock, ("127.0.0.1", 1234), FakeServer(self.service))
        response_head, response_body = sock.output.getvalue().split(b"\r\n\r\n", 1)
        status = int(response_head.split(b" ", 2)[1])
        response_headers = dict(line.decode().split(": ", 1) for line in response_head.split(b"\r\n")[1:])
        data = json.loads(response_body) if response_body else None
        return status, data, response_headers

    def register(self, device=DEVICE_A, token="member-one", environment="sandbox", app=APP):
        return self.request(body={"app": app, "token": device, "environment": environment}, token=token)[0]

    def unregister(self, device=DEVICE_A, token="member-one", app=APP):
        return self.request(method="DELETE", body={"app": app, "token": device}, token=token)[0]

    def send(self, **fields):
        body = {"app": APP, "to": {"user": "memberone000001"}, "title": "€980 · 42 m² · Example street",
                "body": "2 rooms, from 1 Dec.", **fields}
        return self.request("/send", body=body, token=None)

    def user_of(self, device, app=APP):
        found = self.store.device(app, device)
        return found.user if found else None


class DeviceTests(PushTestCase):
    def test_device_language_defaults_to_english_and_updates_at_registration(self):
        body = {"app": APP, "token": DEVICE_A, "environment": "sandbox"}
        for fields, expected in (({}, "en"), ({"language": "de"}, "de"), ({"language": "en"}, "en"),
                                 ({"language": "de"}, "de"), ({}, "en")):
            with self.subTest(fields=fields):
                self.assertEqual(self.request(body={**body, **fields})[0], 204)
                self.assertEqual(self.store.device(APP, DEVICE_A).language, expected)
        # The header controls API sentences; it never sets the device's notification language.
        self.request(body=body, headers={"Accept-Language": "de"})
        self.assertEqual(self.store.device(APP, DEVICE_A).language, "en")
        self.assertEqual(len(self.store.devices(APP)), 1)

    def test_invalid_device_language_is_rejected_without_registering(self):
        for language in ("fr", "DE", "de-DE", "", None, 1, True, [], {}):
            with self.subTest(language=language):
                status, _, _ = self.request(body={"app": APP, "token": DEVICE_A, "environment": "sandbox",
                                                  "language": language})
                self.assertEqual(status, 400)
        self.assertEqual(self.store.devices(APP), [])
        self.assertEqual(self.pb_calls, [])

    def test_register_stores_the_device_for_the_account(self):
        status, data, headers = self.request(body={"app": APP, "token": DEVICE_A, "environment": "sandbox"})
        self.assertEqual(status, 204)
        self.assertIsNone(data)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(self.store.device(APP, DEVICE_A), store.Device(APP, DEVICE_A, "memberone000001", "sandbox"))
        self.assertEqual(self.pb_calls, [("member-one", "192.0.2.10")])

    def test_register_again_refreshes_updated_and_keeps_created(self):
        self.assertEqual(self.register(), 204)
        self.clock.now += 3600
        self.assertEqual(self.register(environment="production"), 204)
        row = self.store._db.execute("SELECT environment, created, updated FROM devices").fetchall()
        self.assertEqual(row, [("production", store.stamp(START), store.stamp(START + 3600))])

    def test_an_account_switch_moves_the_token(self):
        self.register(token="member-one")
        self.assertEqual(self.register(token="member-two"), 204)
        self.assertEqual(self.user_of(DEVICE_A), "membertwo000002")
        self.assertEqual(len(self.store.devices(APP)), 1)
        self.assertEqual(self.send()[1]["sent"], 0)
        self.assertEqual(self.send(to={"user": "membertwo000002"})[1]["sent"], 1)
        self.assertTrue(any("moved from another account" in line for line in self.logs.lines))

    def test_the_same_token_is_separate_per_app(self):
        self.register(app=APP)
        self.register(app="de.ares-empire.empire")
        self.assertEqual(self.store.counts(), {"de.ares-empire.arestemis": 1, "de.ares-empire.empire": 1})

    def test_delete_removes_only_the_accounts_own_device_and_is_always_204(self):
        self.register(token="member-one")
        self.assertEqual(self.unregister(token="member-two"), 204)
        self.assertEqual(self.user_of(DEVICE_A), "memberone000001")
        self.assertEqual(self.unregister(token="member-one"), 204)
        self.assertIsNone(self.store.device(APP, DEVICE_A))
        self.assertEqual(self.unregister(token="member-one"), 204)
        self.assertEqual(self.unregister(device=DEVICE_B), 204)

    def test_an_account_that_lost_the_service_can_still_delete(self):
        self.register()
        self.records["member-one"]["services"] = ["empire"]
        self.clock.now += 61  # past the auth cache
        self.assertEqual(self.register(), 403)
        self.assertEqual(self.unregister(), 204)
        self.assertIsNone(self.store.device(APP, DEVICE_A))

    def test_rejected_or_missing_token_is_401(self):
        for headers in ({"Authorization": "Basic member-one"}, {"Authorization": "Bearer"}, {}):
            with self.subTest(headers=headers):
                for method in ("POST", "DELETE"):
                    status, data, _ = self.request(method=method, token=None, headers=headers,
                                                   body={"app": APP, "token": DEVICE_A, "environment": "sandbox"})
                    self.assertEqual((status, data), (401, {"error": "unauthenticated"}))
        self.assertEqual(self.pb_calls, [])
        self.assertEqual(self.register(token="not-an-account"), 401)
        self.assertEqual(self.unregister(token="not-an-account"), 401)
        with patch.object(self.accounts, "refresh", return_value=(401, {})):
            self.assertEqual(self.register(token="expired"), 401)
        self.assertEqual(self.store.devices(APP), [])

    def test_bearer_is_case_insensitive(self):
        status, _, _ = self.request(token=None, headers={"Authorization": "bEaReR member-one"},
                                    body={"app": APP, "token": DEVICE_A, "environment": "sandbox"})
        self.assertEqual(status, 204)

    def test_an_account_without_the_apps_service_is_403(self):
        self.assertEqual(self.register(token="empire-only"), 403)
        self.assertEqual(self.register(token="empire-only", app="de.ares-empire.empire"), 204)
        self.records["member-two"]["approved"] = False
        self.assertEqual(self.register(token="member-two"), 403)
        with patch.object(self.accounts, "refresh", return_value=(403, {})):
            self.assertEqual(self.register(token="unapproved"), 403)
            self.assertEqual(self.unregister(token="unapproved"), 403)

    def test_login_answers_are_cached_for_a_minute_by_hash(self):
        self.register()
        self.register()
        self.unregister(device=DEVICE_B)
        self.assertEqual(len(self.pb_calls), 1)
        self.assertNotIn("member-one", repr(self.accounts._cache))
        self.clock.now += 61
        self.register()
        self.assertEqual(len(self.pb_calls), 2)
        self.register(token="not-an-account")
        self.register(token="not-an-account")
        self.assertEqual(len(self.pb_calls), 3)  # a rejected token is cached too

    def test_account_server_outage_is_503_and_never_cached(self):
        for answer in ((0, {}), (500, {}), (429, {}), (200, {}), (200, {"record": {"id": ""}}), (200, {"record": []})):
            with self.subTest(answer=answer), patch.object(self.accounts, "refresh", return_value=answer) as refresh:
                self.assertEqual(self.register(), 503)
                self.assertEqual(self.unregister(), 503)
                self.assertEqual(refresh.call_count, 2)
        self.assertEqual(self.accounts._cache, {})

    def test_bad_bodies_are_400_without_asking_the_account_server(self):
        good = {"app": APP, "token": DEVICE_A, "environment": "sandbox"}
        for change in ({"app": "de.example.other"}, {"app": None}, {"app": ["x"]}, {"token": DEVICE_A.upper()},
                       {"token": "ab" * 31}, {"token": "a" * 201}, {"token": "x" * 64}, {"token": 12},
                       {"environment": "staging"}, {"environment": None}):
            with self.subTest(change=change):
                status, data, _ = self.request(body={**good, **change})
                self.assertEqual(status, 400)
                self.assertIn("error", data)
        without_environment = {k: v for k, v in good.items() if k != "environment"}
        self.assertEqual(self.request(body=without_environment)[0], 400)
        self.assertEqual(self.unregister(device="not-hex"), 400)
        for raw, expected in ((b"broken", 400), (b"[]", 400), (b"null", 400), (b"x" * 10_001, 413)):
            with self.subTest(raw=raw[:10]):
                self.assertEqual(self.request(raw=raw)[0], expected)
        self.assertEqual(self.request(body=None)[0], 400)
        self.assertEqual(self.pb_calls, [])

    def test_a_device_token_of_200_hex_chars_is_accepted(self):
        self.assertEqual(self.register(device="0123456789" * 20), 204)


class SendTests(PushTestCase):
    def setUp(self):
        super().setUp()
        self.register(DEVICE_A, "member-one", "sandbox")
        self.register(DEVICE_B, "member-one", "production")
        self.register(DEVICE_C, "member-two", "production")

    def test_localized_text_is_selected_per_device_with_field_fallback(self):
        self.request(body={"app": APP, "token": DEVICE_B, "environment": "production", "language": "de"})
        status, data, _ = self.send(subtitle="Source", localized={"de": {"title": "980 € · 42 m²"}})
        self.assertEqual((status, data), (200, {"sent": 2, "failed": 0, "dry_run": False}))
        english, german = [r["payload"]["aps"]["alert"] for r in self.apple.requests]
        self.assertEqual(english, {"title": "€980 · 42 m² · Example street", "subtitle": "Source",
                                   "body": "2 rooms, from 1 Dec."})
        self.assertEqual(german, {"title": "980 € · 42 m²", "subtitle": "Source", "body": english["body"]})
        outbox = {row["language"]: row for row in self.store.outbox()}
        self.assertEqual(set(outbox), {"en", "de"})
        for language, alert in (("en", english), ("de", german)):
            self.assertEqual(outbox[language]["title"], alert["title"])
            self.assertEqual(outbox[language]["body"], alert["body"])
            self.assertEqual(outbox[language]["result"],
                             {"sent": 1, "failed": 0, "dry_run": False, "removed": 0})

    def test_german_fields_can_override_or_explicitly_clear_each_field(self):
        self.request(body={"app": APP, "token": DEVICE_A, "environment": "sandbox", "language": "de"})
        self.send(subtitle="Source", localized={"de": {"title": "Titel", "subtitle": "Untertitel", "body": "Text"}})
        self.assertEqual(self.apple.requests[0]["payload"]["aps"]["alert"],
                         {"title": "Titel", "subtitle": "Untertitel", "body": "Text"})
        self.apple.requests.clear()
        self.send(subtitle="Source", localized={"de": {"title": "", "subtitle": "", "body": "Text"}})
        self.assertEqual(self.apple.requests[0]["payload"]["aps"]["alert"], {"body": "Text"})

    def test_german_device_without_translation_gets_english_text(self):
        self.request(body={"app": APP, "token": DEVICE_A, "environment": "sandbox", "language": "de"})
        self.send()
        self.assertEqual(self.apple.requests[0]["payload"], self.apple.requests[1]["payload"])
        self.assertEqual({row["language"] for row in self.store.outbox()}, {"en", "de"})

    def test_localized_validation_is_atomic_even_without_german_recipients(self):
        for localized in (None, [], "de", {"en": {}}, {"fr": {}}, {"de": None}, {"de": []},
                          {"de": {"url": "bad"}}, {"de": {"titel": "typo"}}, {"de": {"body": 3}},
                          {"de": {"subtitle": None}}, {"de": {"title": False}},
                          {"de": {"title": "", "body": ""}}, {"de": {"body": "x" * 4096}}):
            with self.subTest(localized=str(localized)[:80]):
                self.assertEqual(self.send(localized=localized)[0], 400)
        self.assertEqual(self.apple.requests, [])
        self.assertEqual(self.store.outbox(), [])

    def test_payload_limit_is_per_variant_and_counts_utf8_bytes(self):
        self.request(body={"app": APP, "token": DEVICE_A, "environment": "sandbox", "language": "de"})
        # Two 2.3 KB alerts together exceed 4 KB, but each delivered notification fits.
        self.assertEqual(self.send(title="", body="x" * 2300, localized={"de": {"body": "y" * 2300}})[0], 200)
        self.apple.requests.clear()
        body = {"app": APP, "to": {"all": True}, "title": "Alert", "localized": {"de": {"body": "ü" * 2050}}}
        self.assertEqual(self.request("/send", raw=json.dumps(body, ensure_ascii=False).encode())[0], 400)
        self.assertEqual(self.apple.requests, [])

    def test_outbox_results_stay_with_the_device_language_on_failure(self):
        self.request(body={"app": APP, "token": DEVICE_B, "environment": "production", "language": "de"})
        self.apple.answers[DEVICE_B] = (410, "Unregistered")
        self.assertEqual(self.send(localized={"de": {"body": "Nachricht"}})[1],
                         {"sent": 1, "failed": 1, "dry_run": False})
        outbox = {row["language"]: row for row in self.store.outbox()}
        self.assertEqual(outbox["en"]["result"], {"sent": 1, "failed": 0, "removed": 0, "dry_run": False})
        self.assertEqual(outbox["de"]["result"], {"sent": 0, "failed": 1, "removed": 1, "dry_run": False})
        self.assertEqual(outbox["de"]["body"], "Nachricht")

    def test_send_to_one_account_builds_apples_request(self):
        status, data, _ = self.send(subtitle="WG-Gesucht", url="arestemis://match/123", thread="matches",
                                    category="ARESTEMIS_MATCH", collapse_id="match-123",
                                    interruption="time-sensitive", sound=True)
        self.assertEqual((status, data), (200, {"sent": 2, "failed": 0, "dry_run": False}))
        self.assertEqual([r["url"] for r in self.apple.requests],
                         ["https://api.sandbox.push.apple.com/3/device/" + DEVICE_A,
                          "https://api.push.apple.com/3/device/" + DEVICE_B])
        request = self.apple.requests[0]
        self.assertEqual(request["payload"], {
            "aps": {"alert": {"title": "€980 · 42 m² · Example street", "subtitle": "WG-Gesucht",
                              "body": "2 rooms, from 1 Dec."},
                    "sound": "default", "thread-id": "matches", "category": "ARESTEMIS_MATCH",
                    "interruption-level": "time-sensitive"},
            "url": "arestemis://match/123"})
        headers = dict(request["headers"])
        self.assertTrue(headers.pop("authorization").startswith("bearer ey"))
        self.assertEqual(headers, {"apns-topic": APP, "apns-push-type": "alert", "apns-priority": "10",
                                   "apns-collapse-id": "match-123", "apns-expiration": str(int(START) + DAY)})

    def test_send_to_all_reaches_every_device_of_the_app(self):
        self.register(DEVICE_D, "member-one", "sandbox", app="de.ares-empire.empire")
        status, data, _ = self.send(to={"all": True})
        self.assertEqual(data, {"sent": 3, "failed": 0, "dry_run": False})
        self.assertEqual(len(self.apple.requests), 3)
        self.assertNotIn(DEVICE_D, json.dumps(self.apple.requests))
        self.assertEqual(self.store.outbox()[0]["user_or_all"], "all")

    def test_passive_is_quiet_and_low_priority(self):
        self.send(interruption="passive", title="", body="Fixed.")
        request = self.apple.requests[0]
        self.assertEqual(request["headers"]["apns-priority"], "5")
        self.assertNotIn("apns-collapse-id", request["headers"])
        self.assertEqual(request["payload"], {"aps": {"alert": {"body": "Fixed."}, "interruption-level": "passive"}})

    def test_defaults_are_active_without_sound(self):
        self.send()
        aps = self.apple.requests[0]["payload"]["aps"]
        self.assertEqual(aps["interruption-level"], "active")
        self.assertNotIn("sound", aps)
        self.assertEqual(self.apple.requests[0]["headers"]["apns-priority"], "10")

    def test_stale_tokens_are_deleted_and_others_kept(self):
        for device in (DEVICE_D, DEVICE_E, DEVICE_F):
            self.register(device, "member-one", "production")
        self.apple.answers = {DEVICE_A: (410, "Unregistered"), DEVICE_B: (400, "BadDeviceToken"),
                              DEVICE_D: (400, "DeviceTokenNotForTopic"), DEVICE_E: (400, "BadCollapseId"),
                              DEVICE_F: (500, "InternalServerError")}
        status, data, _ = self.send()
        self.assertEqual(data, {"sent": 0, "failed": 5, "dry_run": False})
        self.assertEqual({d.token for d in self.store.devices(APP)}, {DEVICE_C, DEVICE_E, DEVICE_F})
        self.assertEqual(self.store.outbox()[0]["result"], {"sent": 0, "failed": 5, "dry_run": False, "removed": 3})

    def test_unreachable_apple_counts_as_failed_and_keeps_the_device(self):
        self.apple.answers = {DEVICE_A: (0, ""), DEVICE_B: (0, "")}
        self.assertEqual(self.send()[1], {"sent": 0, "failed": 2, "dry_run": False})
        self.assertEqual(len(self.store.devices(APP)), 3)

    def test_an_expired_provider_token_is_renewed_and_retried_once(self):
        self.apple.answers = {DEVICE_A: [(403, "ExpiredProviderToken"), (200, "")],
                              DEVICE_B: [(403, "ExpiredProviderToken")]}
        self.assertEqual(self.send()[1], {"sent": 1, "failed": 1, "dry_run": False})
        self.assertEqual(len(self.apple.requests), 4)  # each device at most twice

    def test_send_validation(self):
        for change in ({"app": "de.example.other"}, {"to": {"all": 1}}, {"to": {"all": False}}, {"to": {"user": ""}},
                       {"to": {"user": "a b"}}, {"to": {"user": "x", "all": True}}, {"to": "all"}, {"to": None},
                       {"title": "", "body": ""}, {"title": 5}, {"url": None}, {"interruption": "critical"},
                       {"sound": "yes"}, {"sound": 1}, {"collapse_id": "x" * 65}, {"colapse_id": "typo"},
                       {"body": "x" * 4100}):
            with self.subTest(change=str(change)[:60]):
                status, data, _ = self.send(**change)
                self.assertEqual(status, 400)
                self.assertIn("error", data)
        self.assertEqual(self.apple.requests, [])
        self.assertEqual(self.store.outbox(), [])

    def test_send_needs_no_login_but_is_only_on_the_internal_port(self):
        self.assertEqual(self.send()[0], 200)
        status, _, _ = self.request("/send", body={"app": APP, "to": {"all": True}, "title": "x"},
                                    handler=server.PublicHandler)
        self.assertEqual(status, 404)

    def test_the_outbox_never_holds_device_tokens(self):
        self.send(url="arestemis://match/1")
        self.send(to={"all": True})
        rows = json.dumps(self.store.outbox())
        for device in DEVICES:
            self.assertNotIn(device, rows)


class DeleteAccountTests(PushTestCase):
    """DELETE /internal/accounts/<id>: the account server's call after an account was deleted (docs/ACCOUNTS.md)."""

    EMPIRE = "de.ares-empire.empire"

    def setUp(self):
        super().setUp()
        self.register(DEVICE_A)
        self.register(DEVICE_B, app=self.EMPIRE)
        self.register(DEVICE_C, token="member-two")
        self.send(url="arestemis://match/1")
        self.send(to={"user": "membertwo000002"})
        self.send(to={"all": True})

    def delete(self, account="memberone000001", **kwargs):
        return self.request("/internal/accounts/" + account, method="DELETE", token=None, **kwargs)

    def test_the_accounts_devices_of_every_app_and_its_outbox_rows_go(self):
        self.pb_calls.clear()
        status, data, _ = self.delete()
        self.assertEqual((status, data), (204, None))
        self.assertEqual((self.user_of(DEVICE_A), self.user_of(DEVICE_B, self.EMPIRE)), (None, None))
        self.assertEqual(self.user_of(DEVICE_C), "membertwo000002")
        self.assertEqual(sorted(row["user_or_all"] for row in self.store.outbox()), ["all", "membertwo000002"])
        self.assertEqual(self.pb_calls, [])  # an internal call: no Empire token, no login check
        self.assertIn("deleted account: 2 device(s), 1 outbox row(s)", self.logs.lines)

    def test_an_account_with_nothing_here_is_fine_and_a_repeat_too(self):
        self.assertEqual(self.delete("nobody000000009")[0], 204)
        self.assertEqual(self.delete()[0], 204)
        self.assertEqual(self.delete()[0], 204)
        self.assertEqual(self.store.counts(), {APP: 1})

    def test_an_invalid_account_id_is_400(self):
        for account in ("bad%20id", "z" * 65, "x%2Fy"):
            with self.subTest(account=account):
                status, data, _ = self.delete(account)
                self.assertEqual((status, data), (400, {"error": "Invalid account id."}))
        self.assertEqual(self.store.counts(), {APP: 2, self.EMPIRE: 1})

    def test_only_delete_on_the_internal_port(self):
        self.assertEqual(self.delete(handler=server.PublicHandler)[0], 404)
        self.assertEqual(self.request("/api/push/internal/accounts/memberone000001", method="DELETE")[0], 404)
        self.assertEqual(self.request("/internal/accounts/memberone000001", method="GET", token=None)[0], 405)
        self.assertEqual(self.request("/internal/accounts/", method="DELETE", token=None)[0], 404)
        self.assertEqual(self.request("/internal/accounts/a/b", method="DELETE", token=None)[0], 404)
        self.assertEqual(self.user_of(DEVICE_A), "memberone000001")


class DryRunTests(PushTestCase):
    dry_run = True

    def test_dry_run_records_selected_text_and_language_without_sending(self):
        self.register(DEVICE_A)
        self.request(body={"app": APP, "token": DEVICE_B, "environment": "production", "language": "de"})
        self.assertEqual(self.send(localized={"de": {"body": "2 Zimmer, ab 1. Dez."}})[1],
                         {"sent": 2, "failed": 0, "dry_run": True})
        outbox = {row["language"]: row for row in self.store.outbox()}
        self.assertEqual(outbox["de"]["body"], "2 Zimmer, ab 1. Dez.")
        self.assertEqual(outbox["en"]["body"], "2 rooms, from 1 Dec.")
        self.assertTrue(all(row["result"]["sent"] == 1 and row["result"]["dry_run"] for row in outbox.values()))
        self.assertEqual(self.apple.requests, [])

    def test_dry_run_sends_nothing_and_fills_the_outbox(self):
        self.register(DEVICE_A)
        self.register(DEVICE_B, environment="production")
        status, data, _ = self.send(url="arestemis://match/7")
        self.assertEqual((status, data), (200, {"sent": 2, "failed": 0, "dry_run": True}))
        self.assertEqual(self.apple.requests, [])
        self.assertEqual(self.store.outbox(), [{
            "id": 1, "at": store.stamp(START), "app": APP, "user_or_all": "memberone000001",
            "title": "€980 · 42 m² · Example street", "body": "2 rooms, from 1 Dec.", "url": "arestemis://match/7",
            "language": "en",
            "result": {"sent": 2, "failed": 0, "dry_run": True, "removed": 0}}])
        self.assertEqual(self.send(to={"user": "nobody"})[1], {"sent": 0, "failed": 0, "dry_run": True})

    def test_the_outbox_keeps_the_last_200(self):
        for n in range(205):
            self.send(title=f"Message {n}")
        outbox = self.store.outbox()
        self.assertEqual(len(outbox), 200)
        self.assertEqual(outbox[0]["title"], "Message 204")
        self.assertEqual(outbox[-1]["title"], "Message 5")

    def test_health(self):
        self.register()
        status, data, _ = self.request("/health", method="GET", token=None)
        self.assertEqual((status, data), (200, {"ok": True, "dry_run": True, "devices": {APP: 1}}))


class MigrationTests(PushTestCase):
    def test_old_devices_and_outbox_default_to_english_and_migration_is_repeatable(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = str(Path(directory) / "old.db")
            with sqlite3.connect(path) as db:
                db.executescript("""
                    CREATE TABLE devices (app TEXT NOT NULL, token TEXT NOT NULL, user TEXT NOT NULL,
                        environment TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL, UNIQUE(app, token));
                    CREATE TABLE outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, app TEXT NOT NULL,
                        user_or_all TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, url TEXT NOT NULL,
                        result TEXT NOT NULL);
                """)
                db.execute("INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?)",
                           (APP, DEVICE_A, "memberone000001", "sandbox", store.stamp(START), store.stamp(START)))
                db.execute("INSERT INTO outbox (at, app, user_or_all, title, body, url, result) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (store.stamp(START), APP, "all", "Old title", "Old body", "", '{"sent": 1}'))
            db.close()
            for _ in range(2):
                migrated = store.Store(path, clock=self.clock)
                try:
                    self.assertEqual(migrated.device(APP, DEVICE_A).language, "en")
                    self.assertEqual(migrated.devices(APP)[0].language, "en")
                    self.assertEqual(migrated.outbox()[0]["language"], "en")
                    self.assertEqual(migrated.outbox()[0]["body"], "Old body")
                finally:
                    migrated.close()
            migrated = store.Store(path, clock=self.clock)
            try:
                with patch.object(self.service, "store", migrated):
                    self.assertEqual(self.send(localized={"de": {"body": "Neuer Text"}})[0], 200)
                    self.assertEqual(self.apple.requests[-1]["payload"]["aps"]["alert"]["body"], "2 rooms, from 1 Dec.")
                    self.assertEqual(self.request(body={"app": APP, "token": DEVICE_A, "environment": "sandbox",
                                                       "language": "de"})[0], 204)
                    self.assertEqual(migrated.device(APP, DEVICE_A).language, "de")
            finally:
                migrated.close()


class LanguageTests(PushTestCase):
    def test_accept_language_parsing_through_public_api(self):
        for header, expected in ((None, "en"), ("de", "de"), ("de-DE", "de"),
                                 ("de-DE,de;q=0.9,en;q=0.8", "de"), ("en", "en"),
                                 ("en-GB,de;q=0.5", "en"), ("fr", "en"), ("broken", "en"),
                                 ("fr,de;q=0.8,en;q=0.9", "en"), ("de;q=0.8,en;q=0.8", "de"),
                                 ("en;q=0.8,de;q=0.8", "en"), ("de;q=0", "en"),
                                 ("de;q=oops", "en"), ("de;q=1.1", "en"), ("de;q=-1", "en"),
                                 ("de;q=NaN", "en"), ("DE-de;Q=0.9,en;q=0.8", "de")):
            with self.subTest(header=header):
                status, data, headers = self.request(token=None, body={},
                    headers={"Accept-Language": header} if header is not None else {})
                self.assertEqual((status, data), (401, {"error": "unauthenticated"}))
                self.assertEqual(headers["Content-Language"], expected)

    def test_app_facing_errors_follow_header_including_cached_auth(self):
        cases = [
            ("This account has no access to this app.", "Dieses Konto hat keinen Zugang zu dieser App.", 403,
             (200, {"record": self.records["empire-only"]})),
            ("This account is not active.", "Dieses Konto ist nicht aktiv.", 403, (403, {})),
            ("Login service unavailable, try again in a minute.",
             "Anmeldedienst nicht erreichbar, versuch es in einer Minute noch einmal.", 503, (0, {})),
            ("The account server returned an unreadable answer.",
             "Die Antwort des Anmeldedienstes ist nicht lesbar.", 503, (200, {})),
        ]
        for english, german, status, answer in cases:
            self.accounts._cache.clear()
            with patch.object(self.accounts, "refresh", return_value=answer):
                for language, expected in (("en", english), ("de", german)):
                    with self.subTest(english=english, language=language):
                        result, data, headers = self.request(
                            body={"app": APP, "token": DEVICE_A, "environment": "sandbox"},
                            headers={"Accept-Language": language})
                        self.assertEqual((result, data), (status, {"error": expected}))
                        self.assertEqual(headers["Content-Language"], language)
        for language, expected in (("en", "Internal error."), ("de", "Interner Fehler.")):
            with patch.object(self.service, "register", side_effect=RuntimeError("broken")), \
                    patch.object(server.log, "exception"):
                self.assertEqual(self.request(body={}, headers={"Accept-Language": language})[:2],
                                 (500, {"error": expected}))


class CleanUpTests(PushTestCase):
    def test_devices_not_updated_for_60_days_are_dropped(self):
        self.register(DEVICE_A)
        self.register(DEVICE_B)
        self.clock.now += 30 * DAY
        self.register(DEVICE_B)  # the app re-registered it at launch
        self.clock.now = START + 60 * DAY + 1
        self.assertEqual(self.service.prune(), 1)
        self.assertEqual([d.token for d in self.store.devices(APP)], [DEVICE_B])

    def test_the_daily_loop_runs_until_stopped_and_survives_errors(self):
        stop = threading.Event()
        calls = []

        def prune():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("disk full")
            stop.set()
            return 0

        with patch.object(self.service, "prune", side_effect=prune), patch.object(server.log, "exception"):
            server.clean_up_daily(self.service, stop, every=0)
        self.assertEqual(len(calls), 2)


class ProviderTokenTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.provider = apns.ProviderToken(pem(TEST_KEY), "KEYID12345", "TEAMID1234", clock=self.clock)

    @staticmethod
    def decode(part):
        return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))

    def test_the_token_is_a_valid_es256_jwt(self):
        token = self.provider.get()
        header, claims, signature = token.split(".")
        self.assertEqual(json.loads(self.decode(header)), {"alg": "ES256", "kid": "KEYID12345"})
        self.assertEqual(json.loads(self.decode(claims)), {"iss": "TEAMID1234", "iat": int(START)})
        raw = self.decode(signature)
        self.assertEqual(len(raw), 64)
        der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
        TEST_KEY.public_key().verify(der, f"{header}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))
        other = ec.generate_private_key(ec.SECP256R1()).public_key()
        with self.assertRaises(Exception):
            other.verify(der, f"{header}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))

    def test_the_token_is_reused_for_50_minutes(self):
        first = self.provider.get()
        self.clock.now += 50 * 60 - 1
        self.assertEqual(self.provider.get(), first)
        self.clock.now += 1
        second = self.provider.get()
        self.assertNotEqual(second, first)
        self.assertEqual(json.loads(self.decode(second.split(".")[1]))["iat"], int(START) + 50 * 60)

    def test_renew_replaces_only_the_refused_token(self):
        first = self.provider.get()
        self.provider.renew("some older token")
        self.assertEqual(self.provider.get(), first)
        self.provider.renew(first)
        self.assertNotEqual(self.provider.get(), first)

    def test_only_p256_keys_are_accepted(self):
        with self.assertRaises(ValueError):
            apns.ProviderToken(pem(ec.generate_private_key(ec.SECP384R1())), "KEYID12345", "TEAMID1234")
        with self.assertRaises(ValueError):
            apns.ProviderToken(b"not a key", "KEYID12345", "TEAMID1234")


class RouteTests(PushTestCase):
    def test_the_route_tables_do_not_overlap(self):
        public = {path for _, path in server.PublicHandler.routes}
        internal = {path for _, path in server.InternalHandler.routes}
        self.assertEqual(public, {"/api/push/devices"})
        self.assertEqual(internal, {"/send", "/health", "/internal/accounts/{account}"})
        self.assertEqual(public & internal, set())
        self.assertTrue(all(path.startswith("/api/push/") for path in public))  # all Caddy forwards

    def test_internal_routes_are_unknown_on_the_public_port(self):
        self.register()
        body = {"app": APP, "to": {"all": True}, "title": "x"}
        for method, path in [*server.InternalHandler.routes, ("POST", "/api/push/send"), ("GET", "/api/push/health"),
                             ("DELETE", "/internal/accounts/memberone000001"),
                             ("POST", "/api/push/../send"), ("POST", "/api/push/devices/../../send"),
                             ("POST", "//send"), ("POST", "/send/"), ("POST", "/send?x=1")]:
            with self.subTest(method=method, path=path):
                status, data, _ = self.request(path, method=method, body=body if method == "POST" else None,
                                               handler=server.PublicHandler)
                self.assertEqual(status, 404)
                self.assertEqual(data, {"error": "Unknown route."})
        self.assertEqual(self.apple.requests, [])
        self.assertEqual(self.store.outbox(), [])

    def test_public_routes_are_unknown_on_the_internal_port(self):
        status, _, _ = self.request(body={"app": APP, "token": DEVICE_A, "environment": "sandbox"},
                                    handler=server.InternalHandler)
        self.assertEqual(status, 404)
        self.assertEqual(self.pb_calls, [])

    def test_wrong_method_is_405(self):
        self.assertEqual(self.request(method="GET")[0], 405)
        self.assertEqual(self.request("/send", method="GET", token=None)[0], 405)
        self.assertEqual(self.request("/health", method="POST", token=None, body={})[0], 405)

    def test_both_listeners_bind_loopback_only(self):
        self.assertEqual(HOST, "127.0.0.1")
        for handler in (server.PublicHandler, server.InternalHandler):
            httpd = server.serve(handler, 0, self.service)
            self.addCleanup(httpd.server_close)
            self.assertEqual(httpd.server_address[0], "127.0.0.1")
            self.assertIs(httpd.service, self.service)

    def test_an_unexpected_error_is_500_without_details(self):
        with patch.object(self.service, "health", side_effect=RuntimeError("secret detail")), \
                patch.object(server.log, "exception"):
            status, data, _ = self.request("/health", method="GET", token=None)
        self.assertEqual((status, data), (500, {"error": "Internal error."}))


class ConfigTests(unittest.TestCase):
    def test_defaults_are_the_contracts(self):
        config = Config.from_env({})
        self.assertEqual((config.auth_url, config.db_path, config.public_port, config.internal_port),
                         ("http://127.0.0.1:8090", "/var/lib/empire-push/push.db", 8095, 8096))
        self.assertTrue(config.dry_run)
        self.assertEqual(config.missing_key_settings, ["APNS_KEY_FILE", "APNS_KEY_ID", "APNS_TEAM_ID"])
        self.assertEqual(APPS, {"de.ares-empire.empire": "empire", "de.ares-empire.aresium": "aresium",
                                "de.ares-empire.arestemis": "arestemis", "de.ares-empire.aresus": "aresus"})

    def test_env_overrides_and_any_missing_key_setting_means_dry_run(self):
        env = {"EMPIRE_AUTH_URL": "http://127.0.0.1:9000/", "PUSH_DB": "/tmp/x.db", "PUSH_PUBLIC_PORT": "9095",
               "PUSH_INTERNAL_PORT": "9096", "APNS_KEY_FILE": "/etc/empire-push/AuthKey_KEYID12345.p8",
               "APNS_KEY_ID": "KEYID12345", "APNS_TEAM_ID": "TEAMID1234"}
        config = Config.from_env(env)
        self.assertEqual((config.auth_url, config.public_port, config.internal_port),
                         ("http://127.0.0.1:9000", 9095, 9096))
        self.assertFalse(config.dry_run)
        for name in ("APNS_KEY_FILE", "APNS_KEY_ID", "APNS_TEAM_ID"):
            with self.subTest(missing=name):
                self.assertTrue(Config.from_env({**env, name: "  "}).dry_run)

    def test_make_apns(self):
        with patch.object(server.log, "warning") as warning:
            self.assertIsNone(server.make_apns(Config()))
        self.assertIn("DRY RUN", warning.call_args.args[0])
        # Test files stay in the worktree and are removed on exit.
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            key_file = Path(directory) / "AuthKey_KEYID12345.p8"
            config = Config(key_file=str(key_file), key_id="KEYID12345", team_id="TEAMID1234")
            with self.assertRaises(SystemExit):
                server.make_apns(config)  # set but missing: stop, don't quietly dry-run
            key_file.write_bytes(b"broken")
            with self.assertRaises(SystemExit):
                server.make_apns(config)
            key_file.write_bytes(pem(TEST_KEY))
            with patch.object(server.log, "info"):
                sender = server.make_apns(config)
            self.assertIsInstance(sender, apns.Apns)
            self.assertEqual(sender.token.key_id, "KEYID12345")
            self.addCleanup(sender.transport._client.close)

    def test_logging_keeps_http_libraries_quiet(self):
        with patch.object(logging, "basicConfig"):
            server.configure_logging()
        for name in ("httpx", "httpcore"):
            self.assertGreaterEqual(logging.getLogger(name).getEffectiveLevel(), logging.WARNING)


class TransportTests(unittest.TestCase):
    class Answer(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    def test_auth_refresh_request(self):
        checker = accounts.Accounts("http://127.0.0.1:8090/")
        answer = self.Answer(json.dumps({"record": {"id": "x"}}).encode())
        with patch.object(accounts.urllib.request, "urlopen", return_value=answer) as urlopen:
            self.assertEqual(checker.refresh("fictional-token", "192.0.2.10"), (200, {"record": {"id": "x"}}))
        request = urlopen.call_args.args[0]
        self.assertEqual((request.method, request.full_url),
                         ("POST", "http://127.0.0.1:8090/api/collections/users/auth-refresh"))
        self.assertEqual(request.get_header("Authorization"), "fictional-token")
        self.assertEqual(request.get_header("X-forwarded-for"), "192.0.2.10")
        self.assertEqual(urlopen.call_args.kwargs, {"timeout": 5})

    def test_auth_refresh_failures(self):
        checker = accounts.Accounts("http://127.0.0.1:8090")
        for effect, expected in ((urllib.error.HTTPError("u", 401, "", {}, io.BytesIO(b"{}")), (401, {})),
                                 (OSError("offline"), (0, {})), (self.Answer(b"[]"), (0, {})),
                                 (self.Answer(b"not json"), (0, {}))):
            with self.subTest(effect=type(effect).__name__), patch.object(accounts.urllib.request, "urlopen") as urlopen:
                if isinstance(effect, Exception):
                    urlopen.side_effect = effect
                else:
                    urlopen.return_value = effect
                self.assertEqual(checker.refresh("fictional-token"), expected)

    def test_httpx_transport(self):
        seen = []

        def apple(request):
            seen.append(request)
            if request.url.path.endswith("/down"):
                raise httpx.ConnectError("offline", request=request)
            return httpx.Response(410, json={"reason": "Unregistered"})

        transport = apns.HttpxTransport(httpx.Client(transport=httpx.MockTransport(apple)))
        self.addCleanup(transport._client.close)
        status, body = transport.post("https://api.push.apple.com/3/device/" + DEVICE_A, {"apns-topic": APP}, b"{}")
        self.assertEqual((status, json.loads(body)), (410, {"reason": "Unregistered"}))
        self.assertEqual(seen[0].headers["apns-topic"], APP)
        self.assertEqual(transport.post("https://api.push.apple.com/3/device/down", {}, b"{}"), (0, b""))
        real = apns.HttpxTransport()  # fails here if the http2 extra (h2) is missing
        self.addCleanup(real._client.close)


if __name__ == "__main__":
    unittest.main()
