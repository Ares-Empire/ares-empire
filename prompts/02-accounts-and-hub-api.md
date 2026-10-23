# 02: Per-account hub data, the ring, approvals (accounts + hub server)

Status: merged 2026-10-24; migration applied to the live accounts server; hub server switched after Patrik set admin.
Branch: `codex/02-hub-api` · Worktree: `../ares-empire-02-hub-api` · Model: `gpt-6.1-sol`, effort `high`

## Goal

The server side of `docs/EMPIRE-APP.md`: each account gets its own hub data (`/api/empire` version 2), can add and
remove provinces in its ring, and Patrik approves new accounts from the hub and the phone, with his own login. No
superuser password on the hub or in any app.

## Read first

- `docs/EMPIRE-APP.md` ("How it works underneath"), `docs/API-EMPIRE.md` (the contract: build exactly this), `docs/ACCOUNTS.md`.
- `accounts/pb_migrations/*.js` (the users collection, its rules, `USER_EDITABLE`), `webauth/server.py` (session,
  `_authed`, `_bearer_ok`, `pb_call`, `/api/empire`, `_send_state`, the cache), `deploy/install-accounts.sh`.
- `~/aresium/src/web/empire-auth.ts` and `~/aresium/docs/API-DATA.md` → Auth: the 401 / 403 / 503 rules the hub
  follows too.

## Build

1. **PocketBase migration** (new file in `accounts/pb_migrations/`, with a working `down`):
   - `admin` (bool) and `ring` (JSON, a list of province slugs) on `users`.
   - Nobody but a superuser can set `admin` (on create or update, own or others').
   - A user may update their own `ring` (as their name and password today); `approved`, `services`, `admin` stay off
     limits to them.
   - Admins (`@request.auth.admin = true`) may list and view all users; update **only** `approved` and `services` of
     other accounts (not email, password, name, ring, verified, admin); delete accounts that are not approved yet.
   - Keep the existing `authRule` (verified and approved).
2. **Rules test** `accounts/test-rules.sh`: starts a throw-away PocketBase (path in `$POCKETBASE`, default
   `~/.pocketbase-test/pocketbase`, version 0.40.6, same as the server) on a temp dir and port with
   `accounts/pb_migrations`, creates a superuser, an admin user and a normal user via the API, and checks with curl:
   a user can set their ring but not `approved`/`services`/`admin`; an admin can list pending accounts, approve one,
   delete an unapproved one, but cannot change another user's email, password or `admin`, nor delete an approved
   account; a non-admin cannot list others. Prints PASS/FAIL per check, exits non-zero on any FAIL, cleans up.
3. **Catalog** `webauth/catalog.json` as in `docs/API-EMPIRE.md` (today Aresium `coming-soon`, `app: "aresium://"`).
4. **`webauth/server.py`**, stdlib only:
   - Auth results as in Aresium: allowed / denied 401 / denied 403 / unavailable 503 (never cache "unavailable";
     forward the visitor's IP to PocketBase). The account record from the refresh tells whether it is an admin.
   - `GET /api/empire` version 2 per account, merging `data/state.json` (or the seed fallback) with the catalog and
     the account's `ring`, exactly per the contract (`projects`, `addable`, `chronicle` filtered by the ring's
     slugs for non-admins, `ideas` admin only, `pending` count for admins, `state`, `app`).
   - `POST /api/empire/ring {add|remove}`: validate against the catalog, write the account's own `ring` in
     PocketBase **with the visitor's token**, return the new `EmpireData`.
   - `GET /api/empire/approvals`, `POST /api/empire/approvals/:id {approve|decline}`: admin only (403 otherwise),
     performed against PocketBase **with the admin's own token**; approve sets `approved: true` and
     `services: ["empire"]`.
   - `live`: for provinces with a pulse (today Aresium: `GET https://aresium.de/api/pulse` with the visitor's token,
     2 s timeout, answer `{line}`), cached per account for 60 s; on any failure `live: null`, never an error.
     (Aresium's `/api/pulse` is built separately; until it exists the call fails quietly and `live` is null.)
5. **Tests** (`python3 -m unittest`, in `webauth/test_server.py`, stdlib only, PocketBase faked): per-account
   filtering (admin all, user ring ∩ catalog, `addable`, chronicle filter, no ideas, `pending`), ring add/remove incl.
   a non-catalog slug refused, approvals 403 for non-admins, the three auth statuses, `live` failure → null.

## Settled: do not re-open

- Approvals and ring writes use the caller's own token; no superuser credentials anywhere.
- The catalog lives in `webauth/catalog.json`, not in `data/state.json`.
- Version-1 field names stay, so the desktop hub keeps working.

## Out of scope

- The hub's web UI (brief 01 runs in parallel and owns `web/`), Aresium's `/api/pulse`, the iPhone app.
- Deploying or touching the live PocketBase; Claude applies the migration after testing it on a copy.

## Rules (no sandbox: these are rules, not walls)

Work only inside the worktree (plus the throw-away PocketBase temp dir). Never commit, push or change git config.
Install nothing (the PocketBase binary is already at `~/.pocketbase-test/pocketbase`). Network only to that local
PocketBase. No secrets or personal data in files.

## Done when

- `bash accounts/test-rules.sh` prints only PASS; `python3 -m unittest webauth/test_server.py` passes.
- Final message: files changed, the exact test output summaries, anything doubtful (especially about the rules).
