# Empire push — one push service for every app

**Decided 2026-10-24** with Patrik, for the Arestemis and Aresus apps (Telegram retires once push works on the phone).
Status (2026-10-24): **deployed** as `empire-push.service`, a dry run until the APNs key exists; Aresus and Arestemis send through it. Code: `push/` in this repo; Swift side:
`empire-ios/Shared/Push/`.

## Why one service

Every Empire app may send notifications (Arestemis: a new flat; Aresus: a province has an issue, a sync failed;
later Aresium). Apple needs one signing key (`.p8`) per developer team for all apps, a list of device tokens per app
and per account, and clean-up when a token goes stale. Doing that once here, instead of a copy in every service, is
the "good structure" rule ([EMPIRE.md → How we build apps](../EMPIRE.md#how-we-build-apps-web--ios)).

## Shape

```
iPhone app ──POST /api/push/devices (Empire token)──▶ Caddy (www.ares-empire.de) ──▶ push service :8095 (public part)
province service (Arestemis, Aresus, …) ──POST /send──▶ push service :8096 (127.0.0.1 only, never routed by Caddy)
account server (PocketBase) ──POST /send, DELETE /internal/accounts/<id>[/devices[/arestemis]]──▶ push service :8096
push service ──HTTP/2, ES256 token──▶ Apple (api.push.apple.com / api.sandbox.push.apple.com)
```

- **Runs as** `empire-push.service` (systemd, user `empire-push`), code `push/` in this repo, copied by
  `deploy/install-push.sh` to `/opt/empire-push/push/` (the service user cannot read `/root`), venv
  `/opt/empire-push/venv` (`httpx[http2]`, `cryptography`), data `/var/lib/empire-push/push.db` (SQLite). Config from
  `/root/ares-empire/push/.env` (not in git, optional; `push/.env.example` lists the settings).
- **Until Apple approves the developer account** there is no key: the service runs in **dry-run** (logs and keeps the
  last 200 messages in an `outbox` table, sends nothing). Adding the key = put the `.p8` on the server
  (`/etc/empire-push/AuthKey_<KEYID>.p8`, mode 600), set `APNS_KEY_ID`, `APNS_TEAM_ID`, restart.

## Public API (apps)

### Language

API error sentences follow `Accept-Language`; responses set `Content-Language: en|de`. Among English/German tags,
the highest `q` wins (first on a tie); unsupported or unreadable headers fall back to English. Codes such as
`unauthenticated` and developer validation messages stay unchanged. The header does not set notification language:
that is registered per device below.

Auth: `Authorization: Bearer <Empire token>`, checked like every service checks a login
([ACCOUNTS.md → How a service checks a login](ACCOUNTS.md#how-a-service-checks-a-login)): `auth-refresh` must answer 200
and the account's `services` must contain the service of that app (table below). Cached 60 s per token.

| App (`app` = bundle id) | needs service |
|---|---|
| `de.ares-empire.empire` | `empire` |
| `de.ares-empire.aresium` | `aresium` |
| `de.ares-empire.arestemis` | `arestemis` |
| `de.ares-empire.aresus` | `aresus` |

- `POST /api/push/devices` `{app, token, environment: "sandbox" | "production"}` → `204`. `token` is the APNs device
  token as lowercase hex (64–200 chars). Upsert by `(app, token)`: the newest account wins (a phone that switches
  account moves its token). Apps call this at every launch while signed in, so `updated` shows the device is alive.
- **CONTRACT ADDITION (2026-10-24, languages):** registration accepts optional `language: "en" | "de"`, default `en`;
  any other value is `400`. Existing device rows migrate to `en`. Every upsert updates the language, including
  resetting it to `en` when omitted. Example: `{"app":"de.ares-empire.arestemis","token":"<APNs lowercase hex>",
  "environment":"sandbox","language":"de"}`. Apps re-register at launch after a language change.
- `DELETE /api/push/devices` `{app, token}` → `204` (always, also when unknown). Apps call it on log out, and when their
  service answers 403 (the account lost access). **CONTRACT ADDITION (2026-10-24):** it needs a valid login but not the
  app's service (else an account that lost access could not remove its device), and it removes the device only while
  it is registered to that account (a later account keeps a token it took over). A login that is already invalid
  cannot remove it: that device stays until another account registers it or the 60-day clean-up.
- **Central logout (2026-10-26, `empire-ios` brief 09):** each app records its accepted device in the shared App Group
  (`empire.push.devices`: bundle id → APNs device token, never an Empire token). When a person logs out in any app,
  that app removes **every** recorded app's device with the login that just ended (the same account for all apps), so
  notifications stop also for apps that are not running. An app following a logout made elsewhere removes its own.
  **Limit:** one try per device; a failed removal (offline, 5xx) is logged and dropped from the record, so that device
  stays registered until another account registers it or the 60-day clean-up. A logout because the login was refused
  sends no removals (the token is invalid).
- Errors: `401` token rejected, `403` the account lacks the app's service, `400` bad body, `503` account server down.

Both push listeners accept bodies up to **10,000 bytes**, checked from one decimal `Content-Length` before reading.
POST needs the length; malformed or repeated lengths, transfer encoding, and incomplete bodies are `400`;
an oversized body is `413`. Headers and body each have an absolute **5-second** read deadline (body timeout `408`;
incomplete headers close the connection). Each listener has **16** request workers and its own slots; excess
connections receive `503` immediately, with `Retry-After: 1`. The listen backlog is 32. Responses have a 5-second
socket write timeout and each connection handles one request. Registration bodies are small; the send limit allows
the English and German notification payloads, each subject to Apple's separate 4 KB check.

Public requests also have per-client limits: **4 concurrent**, a token bucket replenished at **1 request/second**,
and a **20-request burst**. Concurrency refusal is `503`, rate refusal is `429`, both before reading the body.
Client bookkeeping is bounded to 4096 entries. Internal services share the loopback address, so that listener uses
the global cap only. The hub uses **8 concurrent requests per client**, **4 requests/second**, and an **80-request
burst**, allowing its page's asset requests while keeping worker slots available for other clients.

`AUTH_TRUSTED_PROXY` lists the exact peer IP addresses allowed to supply Caddy's `X-Forwarded-For`. Defaults are
`127.0.0.1,::1`; the hub's unit also includes `172.18.0.1` for its bridge listener. Only the last address Caddy appends
is used; other peers use their socket address. Malformed or repeated forwarded headers use the socket address.
The same identity is used for admission and account-server forwarding. Confirm Caddy's actual source address when
installing the hub unit; Caddy's buffering and read timeouts are configured separately by the server operator.

## Internal API (province services on the same host)

`POST http://127.0.0.1:8096/send`, JSON:

```json
{
  "app": "de.ares-empire.arestemis",
  "to": {"user": "<PocketBase user id>"} ,
  "title": "€980 · 42 m² · Schwabing",
  "subtitle": "WG-Gesucht",
  "body": "2 rooms, from 1 Dec. Fits your search.",
  "localized": {
    "de": {"title": "980 € · 42 m² · Schwabing", "body": "2 Zimmer, ab 1. Dez. Passt zu deiner Suche."}
  },
  "url": "arestemis://match/123",
  "thread": "matches",
  "category": "ARESTEMIS_MATCH",
  "collapse_id": "match-123",
  "interruption": "time-sensitive",
  "sound": true
}
```

- `to` is `{"user": id}` (that account's devices of this app) or `{"all": true}` (every device registered for this app).
  No app sends to `all` since 2026-10-25: Aresus sends each push once per owner (its `EMPIRE_ALLOWED_USERS`), since any
  account with the `aresus` service could register a device.
- **CONTRACT ADDITION (2026-10-24, languages):** optional `localized: {"de": {"title"?, "subtitle"?, "body"?}}` supplies
  German strings as in the example. A `de` device gets each supplied field; omitted fields fall back independently
  to the top-level English text. An empty string clears that field. English devices always get top-level text.
  Only `de` and those three string fields are allowed; unknown languages/fields, non-objects and non-string values
  are `400`. Both resulting notifications must have a title or body and fit Apple's 4 KB limit (UTF-8 bytes,
  including the rest of the payload); all validation happens before any delivery, even with no recipients.
- `interruption`: `passive | active | time-sensitive` (default `active`; `passive` also sends with low priority). `url`
  is handed to the app when the notification is tapped. `category` names actions the app registered (e.g. "Open
  listing"). `sound: true` plays the default sound (default `false`). `title` or `body` is required; every other field
  is optional. Unknown fields are a `400`, so a misspelt one is noticed. `collapse_id` at most 64 bytes, the whole
  notification at most 4 KB (Apple's limits).
- Answer: `{"sent": n, "failed": n, "dry_run": bool}`; in a dry run `sent` counts the devices it would have reached.
  Stale tokens (Apple `410`, or `400 BadDeviceToken` / `DeviceTokenNotForTopic`) are deleted. Tokens not refreshed for
  60 days are dropped daily.
- `GET http://127.0.0.1:8096/health` → `{"ok": true, "dry_run": bool, "devices": {"<app>": n}}` (**CONTRACT ADDITION**,
  for the install script and monitoring).
- `DELETE http://127.0.0.1:8096/internal/accounts/<id>` → `204` (2026-10-25): the account server's call after an
  Empire account was deleted ([ACCOUNTS.md → Accounts in every app](ACCOUNTS.md#accounts-in-every-app)). That
  account's devices of every app go, and its outbox rows with them (they hold the texts sent to it); `204` also when
  there is nothing. `400` for an id that is not 1–64 of `A–Z a–z 0–9 _ -`. No login; internal port only. Leaving
  Arestemis also follows the access-change jobs below; the app removes its own device on logout as before.
- `DELETE http://127.0.0.1:8096/internal/accounts/<id>/devices` → `204`: removes that account's device
  registrations for every app after approval is removed.
- `DELETE http://127.0.0.1:8096/internal/accounts/<id>/devices/arestemis` → `204`: removes only that account's
  Arestemis registrations after its `arestemis` service is removed. Other app names are `400`.
  Both device-removal routes preserve the outbox, are idempotent, and use the same id validation as account deletion.
  They require one **`X-Empire-Access-Generation`** header: a decimal integer from 1 through 9007199254740991 (`400`
  for missing, repeated, or invalid). They clear cached approvals and compare the generation under that account's
  lock. Authentication runs before acquiring the lock, and its returned `access_generation` must pass the stored
  fence before registration. Unrelated accounts' authentication never holds this lock.
  SQLite's `account_access` table persists the highest generation, applied removal scope, and deletion marker.
  A call older than authenticated activity, or a repeat of the applied generation, answers **204 without removing
  devices**. A fresh authorized registration advances the fence; account deletion keeps a marker that refuses late
  registrations. These small markers survive restart along with the device database.
  No login; internal loopback listener only, never routed by Caddy, and
  `404` on the public listener. PocketBase plans these calls as retryable jobs in **deletions**, run by the existing
  **empire-deletions** cron ([ACCOUNTS.md → Taking away access](ACCOUNTS.md#taking-away-access-reaches-arestemis-and-push)).
- Never logs a device token or an Empire token in full.

## Who sends what

| Sender | App | To | When |
|---|---|---|---|
| Arestemis | `de.ares-empire.arestemis` | the account whose hunt found it | a new match ([ARESTEMIS-APP.md](ARESTEMIS-APP.md)) |
| Aresus | `de.ares-empire.aresus` | each owner (`EMPIRE_ALLOWED_USERS`) | an issue opens or is fixed, an Aresync run fails |
| Account server (2026-10-25) | `de.ares-empire.empire` | the account itself | it was approved, or given more apps |

**The account server's notification** (Patrik, 2026-10-25/26; `accounts/pb_hooks/lib/push.js`, sent from
`accounts.pb.js` next to the email, [ACCOUNTS.md → Notifications](ACCOUNTS.md#notifications-2026-10-25)): only to an
account about itself. Sign-ups and access requests reach Patrik by email, not as notifications (Patrik, 2026-10-26).

```json
{"app": "de.ares-empire.empire", "to": {"user": "<account id>"},
 "title": "Arestemis is ready", "body": "Open the Empire app to start.",
 "localized": {"de": {"title": "Arestemis ist bereit", "body": "Öffne die Empire-App, um loszulegen."}},
 "url": "empire://ring", "thread": "access", "collapse_id": "ready-<account id>"}
```

- Approved for the first time: every app the account has now; given more apps: the new ones. Several: "Ares Empire
  and Arestemis are ready" / "… sind bereit". No category, no sound.
- An account can register its Empire-app device only once it is approved (login needs approval), so the first approval
  usually reaches no device yet (the email tells it); "more apps" reaches the phone.

Timeout 3 s; a failure (the push service down or refusing) is logged by the account server as `push failed` and never
fails the request that caused it. The address is the push service's in `accounts/pb_hooks/lib/deletions.js`
(`PUSH_INTERNAL_URL` overrides it, only in the tests).

## iPhone side (`empire-ios/Shared/Push/`)

One `PushCenter` used by every app: asks for permission once the user is signed in (alert, sound, badge;
time-sensitive delivery needs the app's `com.apple.developer.usernotifications.time-sensitive` entitlement, since
iOS 15 it is no longer a permission), registers with Apple, sends the token to `/api/push/devices` (sandbox in Debug,
production in Release), deletes it on log out, and turns a tapped notification's `url` into a deep link the app
handles. Needs the Push Notifications capability (`aps-environment`), which needs the paid team; until then the
simulator is tested with `xcrun simctl push <udid> <bundle id> payload.apns`.

## Operating

- **Install or update** (also after every change in `push/`, `empire_language.py`, or `empire_http.py`):
  `sudo bash deploy/install-push.sh`.
  It creates the user,
  `/opt/empire-push` (venv + code), `/var/lib/empire-push`, `/etc/empire-push`, installs the unit, restarts the service
  and prints `/health`. Caddy, inside the `ares-empire.de, www.ares-empire.de` site and before the hub's catch-all:

  ```
  handle /api/push/* {
      reverse_proxy 127.0.0.1:8095
  }
  ```
- **Logs:** `journalctl -u empire-push -f` (tokens appear only as their first 6 characters). Last messages, also in a
  dry run: `sudo sqlite3 /var/lib/empire-push/push.db "SELECT at, app, user_or_all, language, title, result FROM outbox
  ORDER BY id DESC LIMIT 20"`. Each send records one row per recipient language, with the selected title/body and
  that language's counts; a `de` row may contain English fallback fields. Sends with no recipients keep an `en` row
  with zero counts. Old outbox rows migrate to `en`. The last 200 rows stay; no device tokens are stored there.
- **Adding the key** (once Apple approved the team): developer.apple.com → Keys → a key with "Apple Push Notifications
  service", download `AuthKey_<KEYID>.p8` (only once possible). Then on the server:
  `sudo install -m 600 -o empire-push -g empire-push AuthKey_<KEYID>.p8 /etc/empire-push/`, set `APNS_KEY_FILE`,
  `APNS_KEY_ID`, `APNS_TEAM_ID` in `push/.env`, `sudo systemctl restart empire-push`; `/health` then says
  `"dry_run": false`. A key that is set but unreadable stops the service (see the journal) instead of quietly not
  sending.
- **Tests** (Mac or server): `python3 -m venv .venv && .venv/bin/pip install -r push/requirements.txt`, then
  `.venv/bin/python -m unittest push/test_push.py test_empire_http.py`. Job unit checks:
  `node --test accounts/test_jobs.js`; PocketBase integration and rollback/reapply: `bash accounts/test-rules.sh`.

The hub uses the same body cap and deadlines through `empire_http.py`, with **32** workers. Its login, sign-up and
reset forms and JSON API fit the 10,000-byte cap. Restart `ares-empire` after updating that shared module or
`webauth/server.py`.

### Accounts rollout (2026-10-25, lead, on the server)

Install this push service (`sudo bash deploy/install-push.sh`) **before** the account server's deletion jobs: the
account server takes a 404 as "nothing to delete", so a call to a push service without the route would close the job.
Check with a made-up id (nothing is deleted): `curl -s -o /dev/null -w '%{http_code}\n' -X DELETE
http://127.0.0.1:8096/internal/accounts/deploycheck0001` → `204`, and `curl -s -o /dev/null -w '%{http_code}\n' -X DELETE
http://127.0.0.1:8095/internal/accounts/deploycheck0001` → `404` (not on the public port).

### Language rollout (lead, on the server)

Deploy this push service **before the provinces** start sending `localized`, or the previous service will reject
their requests. The hub restarts through its existing deployment after the lead pushes the merged change to `main`;
the push service still needs its explicit install step. From the updated `/root/ares-empire` checkout:

```bash
sudo bash deploy/install-push.sh
sudo systemctl is-active empire-push
curl -fsS http://127.0.0.1:8096/health
sudo sqlite3 /var/lib/empire-push/push.db "SELECT language, COUNT(*) FROM devices GROUP BY language"
sudo sqlite3 /var/lib/empire-push/push.db "SELECT language, COUNT(*) FROM outbox GROUP BY language"
```

Check acceptance without notifying any device (an unused fixture account, no `all` broadcast):

```bash
curl -fsS http://127.0.0.1:8096/send -H 'Content-Type: application/json' \
  --data '{"app":"de.ares-empire.empire","to":{"user":"languagecheck00"},"title":"Language check","localized":{"de":{"title":"Sprachprüfung"}}}'
curl -sS -D - -X POST http://127.0.0.1:8095/api/push/devices -H 'Accept-Language: de' \
  -H 'Content-Type: application/json' --data '{}'
```

Expect `{"sent":0,"failed":0,"dry_run":...}` for the first and `401`, `Content-Language: de`,
`{"error":"unauthenticated"}` for the second. Confirm no delivery in the zero-count outbox row. Then deploy the
province language changes. With a test phone registered in German, inspect its next expected notification and the
`de` outbox row's selected text and counts (including dry run); no test broadcast is needed.

For the hub after its automatic deployment:

```bash
sudo systemctl is-active ares-empire
curl -sS -D - http://172.18.0.1:5185/api/empire -H 'Accept-Language: de'
rg 'Accept-Language' web/app/empire-api.js
```

The unauthenticated API check is `401` with `Content-Language: de`; the website script contains the explicit `en`
header. In an authenticated Empire app, compare `en` and `de` `/api/empire` responses: `Content-Language` and live
lines follow the request (an Aresus issue starts with `Problem: ` in German). Province texts/chronicle/ideas remain
English. The English website must keep English lines in a German browser. Use an existing authenticated session;
never paste or log its token. If either service fails, inspect `journalctl -u empire-push -n 50` or
`journalctl -u ares-empire -n 50` respectively.
