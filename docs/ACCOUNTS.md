# Empire accounts — one login for every service

**Planned 2026-10-23.** Status: **server running** at https://auth.ares-empire.de (PocketBase).
The hub and Aresium (website + API) log in with it; their old shared passwords are gone (2026-10-23). Replaces the "Empire SSO" expansion.

## Goal

Ares Empire is the single place where people have an account. Every connected service (and
every iPhone app) trusts that login, so nobody signs in twice and each service never stores
passwords itself.

## How it should work

- **Sign up** with email + password on the Empire. New accounts start as *pending*.
- **Patrik approves** each new account (e.g. a Telegram message with an approve button).
  Until then the account can't use anything.
- **Web:** the hub already hands a short-lived signed token to a service (`/sso?token=…`,
  Aresium verifies it today). That stays, but carries the user's id instead of "the one user".
- **iPhone apps:** log in against the Empire, get a token, send it with every API request
  to the service.
- **Per-service access:** an account can be allowed into some services and not others.
- Needed for the App Store / for other users later: password reset by email, and deleting
  your own account.

## Connected services

The live table is in [`EMPIRE.md` → Connections](../EMPIRE.md#connections). Rule of thumb:
a service counts as *connected* once it accepts Empire logins and no longer has its own password.

## What is built (2026-10-23)

- **PocketBase** 0.40.6 (self-hosted, one binary, SQLite) as systemd unit `empire-accounts`,
  on `127.0.0.1:8090`, behind Caddy at `auth.ares-empire.de`. Admin UI: https://auth.ares-empire.de/_/
- Install/update: `deploy/install-accounts.sh` (pinned version + SHA-256). The account rules are the
  migration in `accounts/pb_migrations/`, applied automatically on start.
  PocketBase stops publishing on GitHub after 0.40.6; future versions come from the author's own site.
- Data: `/var/lib/empire-accounts/pb_data` (not in git). Must be part of the off-server backup.
- **Users** (`users` collection): email + password, plus
  - `approved` — set only by a superuser; login needs `verified = true && approved = true`.
  - `services` — which provinces the account may use (`empire`, `aresium`; add more in a new migration).
  - Users can rename themselves, change password, delete their account. They can't touch
    `approved`/`services`/`verified`, and can only see their own record (tested).
- **Email**: Resend via `smtp.resend.com:2465` (the host blocks outgoing 25/465/587), domain
  `ares-empire.de` (DNS at Hetzner), sender `noreply@ares-empire.de`. The
  SMTP key is entered only in the admin UI (Settings → Mail settings), never in git or chat.

## Website flow

- `/login` → *Log in* button + "New account? Sign up". `/login/email` → email + password.
- `/signup` (hub only) creates the account and sends the confirmation email. A hook
  (`accounts/pb_hooks/accounts.pb.js`) emails the superusers an approval request with a direct link,
  and emails the person once `approved` is switched on.
- `/forgot` (hub only) sends PocketBase's reset email; its links open PocketBase's own pages
  at auth.ares-empire.de/_/#/auth/….
- Hub → province: `/sso?to=aresium` POSTs the visitor's token to `aresium.de/sso` (never in a URL).
- PocketBase also emails "login from a new location" alerts (built in, on by default).

## How a service checks a login

A token stays valid until it expires (7 days) even if the account is un-approved meanwhile, so a
service must not trust the token alone. It calls
`POST https://auth.ares-empire.de/api/collections/users/auth-refresh` with the token: a 200 means
approved and verified (the auth rule runs again), and the returned record's `services` must contain
the service's name. Cache the answer for a few minutes per token.
The hub's `GET /api/empire` (provinces, ideas, chronicle) takes the same Bearer token, for an Empire app.
Reference implementation: `aresium/src/web/empire-auth.ts` (also limits access to the user ids in
`EMPIRE_ALLOWED_USERS` while Aresium holds only one person's data).

## Open questions (decide when building)

- For multi-user Aresium: which data is per person (transactions, accounts, rules) and
  which is shared (the category list).
