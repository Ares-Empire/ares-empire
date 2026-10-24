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
- `DELETE /api/push/devices` `{app, token}` → `204` (always, also when unknown). Apps call it on log out, and when their
  service answers 403 (the account lost access). **CONTRACT ADDITION (2026-10-24):** it needs a valid login but not the
  app's service (else an account that lost access could not remove its device), and it removes the device only while
  it is registered to that account (a later account keeps a token it took over). A login that is already invalid
  cannot remove it: that device stays until another account registers it or the 60-day clean-up.
- Errors: `401` token rejected, `403` the account lacks the app's service, `400` bad body, `503` account server down.

## Internal API (province services on the same host)

`POST http://127.0.0.1:8096/send`, JSON:

```json
{
  "app": "de.ares-empire.arestemis",
  "to": {"user": "<PocketBase user id>"} ,
  "title": "€980 · 42 m² · Schwabing",
  "subtitle": "WG-Gesucht",
  "body": "2 rooms, from 1 Dec. Fits your search.",
  "url": "arestemis://match/123",
  "thread": "matches",
  "category": "ARESTEMIS_MATCH",
  "collapse_id": "match-123",
  "interruption": "time-sensitive",
  "sound": true
}
```

- `to` is `{"user": id}` (that account's devices of this app) or `{"all": true}` (every device registered for this app;
  Aresus uses it, since only accounts with the `aresus` service can register).
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
- Never logs a device token or an Empire token in full.

## iPhone side (`empire-ios/Shared/Push/`)

One `PushCenter` used by every app: asks for permission once the user is signed in (alert, sound, badge;
time-sensitive delivery needs the app's `com.apple.developer.usernotifications.time-sensitive` entitlement, since
iOS 15 it is no longer a permission), registers with Apple, sends the token to `/api/push/devices` (sandbox in Debug,
production in Release), deletes it on log out, and turns a tapped notification's `url` into a deep link the app
handles. Needs the Push Notifications capability (`aps-environment`), which needs the paid team; until then the
simulator is tested with `xcrun simctl push <udid> <bundle id> payload.apns`.

## Operating

- **Install or update** (also after every change in `push/`): `sudo bash deploy/install-push.sh`. It creates the user,
  `/opt/empire-push` (venv + code), `/var/lib/empire-push`, `/etc/empire-push`, installs the unit, restarts the service
  and prints `/health`. Caddy, inside the `ares-empire.de, www.ares-empire.de` site and before the hub's catch-all:

  ```
  handle /api/push/* {
      reverse_proxy 127.0.0.1:8095
  }
  ```
- **Logs:** `journalctl -u empire-push -f` (tokens appear only as their first 6 characters). Last messages, also in a
  dry run: `sudo sqlite3 /var/lib/empire-push/push.db "SELECT at, app, user_or_all, title, result FROM outbox ORDER BY
  id DESC LIMIT 20"`.
- **Adding the key** (once Apple approved the team): developer.apple.com → Keys → a key with "Apple Push Notifications
  service", download `AuthKey_<KEYID>.p8` (only once possible). Then on the server:
  `sudo install -m 600 -o empire-push -g empire-push AuthKey_<KEYID>.p8 /etc/empire-push/`, set `APNS_KEY_FILE`,
  `APNS_KEY_ID`, `APNS_TEAM_ID` in `push/.env`, `sudo systemctl restart empire-push`; `/health` then says
  `"dry_run": false`. A key that is set but unreadable stops the service (see the journal) instead of quietly not
  sending.
- **Tests** (Mac or server): `python3 -m venv .venv && .venv/bin/pip install -r push/requirements.txt`, then
  `.venv/bin/python -m unittest push/test_push.py`.
