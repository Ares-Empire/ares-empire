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
  - `approved` — set by a superuser or an admin approving another account; login needs
    `verified = true && approved = true`.
  - `services` — which provinces the account may use (`empire`, `aresium`, `arestemis`, `aresus`, `arestoteles`; add
    more in a new migration).
  - `admin` — only a superuser may set this, including at sign-up.
  - `ring` — JSON list of province slugs, editable by the account itself. Adding a province does not grant access.
  - Normal users can rename themselves, change password and delete their account. They can't touch
    `approved`/`services`/`verified`/`admin`, and can only see their own record.
  - Admins can list/view all accounts, update only `approved` and `services` on other accounts, and delete
    unapproved accounts. An admin cannot delete an approved account, including their own.
    The `admin-visibility.pb.js` hook exposes account emails to admins for approvals without granting
    PocketBase's broader `manageRule` privileges.

Local verification (no live account data): `bash accounts/test-rules.sh` uses a disposable PocketBase 0.40.6
from `$POCKETBASE` (default `~/.pocketbase-test/pocketbase`) and checks API rules, email visibility and migration
rollback/reapply. It loads the visibility hook and the feedback and contact hooks (their mail goes to a local SMTP
sink the script starts; never Resend, never the system's sendmail) but not the sign-up mail hooks. Hub contract tests use fake
PocketBase responses: `python3 -m unittest webauth/test_server.py`.
- **Email**: Resend via `smtp.resend.com:2465` (the host blocks outgoing 25/465/587), domain
  `ares-empire.de` (DNS at Hetzner), sender `noreply@ares-empire.de`. The
  SMTP key is entered only in the admin UI (Settings → Mail settings), never in git or chat.

## Contact & support (`feedback`, 2026-10-24)

Every app's Settings has "Contact & support": the person picks a kind and writes a message, the app sends it to the
account server, and Patrik gets it by email. Migration `1793100000_feedback.js`, hook `pb_hooks/feedback.pb.js`.

- **Collection `feedback`:** `user` (the account; required; deleted with it), `app` (`empire`, `aresium`, `arestemis`,
  `aresus`, `arestoteles`; required), `kind` (`problem`, `idea`, `question`, `other`; required), `message` (1–5000
  characters, not only blanks), `app_version` (≤ 40), `system` (≤ 80, e.g. "iOS 27.0 · iPhone"), `language` (`en`,
  `de`), `created`.
- **Rules:** create only with a login of a verified, approved account, and only as itself
  (`@request.body.user = @request.auth.id`; approval is checked again on every request, so an account switched to
  unapproved cannot send with its old token). List, view, update and delete: superusers only. Patrik reads them in the
  admin UI (Collections → feedback).
- **Rate limit:** at most 10 creates per hour per client IP (rule `feedback:create`, 3600 s, in Settings → Rate limits,
  added by the migration). The app shows "too many messages, try later" on the 429.
- **Email:** after each create the hook mails it to `REDACTED-EMAIL` (the constant `TO` in `pb_hooks/mail.js`,
  shared with the contact hook) from the
  server's sender, `Reply-To` the account's email, subject `[Arestoteles] Idea: <first words>`, a plain body (kind,
  app, version, system, language, account email, the message, a link to the record). A failed email is logged
  (`feedback email failed` in the admin UI's logs) and the record stays; the create never fails because of mail.
- App side: `empire-ios` `Shared/Support/` (`POST /api/collections/feedback/records` with the Empire token).

## Website contact form (`contact`, 2026-10-25)

Anyone can write to Patrik without an account at www.ares-empire.de/kontakt (German) or /contact (English); the imprint
names it as the second quick way to reach him besides email. The page posts straight to the account server
(`POST /api/collections/contact/records`, no login; PocketBase allows cross-origin requests). Migration
`1793200000_contact.js`, hook `pb_hooks/contact.pb.js`.

- **Collection `contact`:** `name` (optional, ≤ 100), `email` (required, checked as an email address), `message`
  (1–5000 characters, not only blanks), `language` (`en`, `de`), `website` (the honeypot: the form hides it from
  people, any text in it is refused), `created`.
- **Rules:** create open to everyone; list, view, update and delete for superusers only. Patrik reads them in the admin
  UI (Collections → contact).
- **Rate limit:** at most 5 creates per hour per visitor address (rule `contact:create`, 3600 s). The address is the
  visitor's: Caddy's `X-Forwarded-For`, trusted since the first migration (`trustedProxy`, rightmost entry).
- **Email:** after each create the hook mails it to Patrik (`pb_hooks/mail.js`) from the server's sender, `Reply-To`
  the given address, subject `[Website] Kontakt: <first words>` (German page) or `[Website] Contact: …`, a plain body
  (name, email, language, the message, a link to the record). A failed email is logged (`contact email failed`) and
  the record stays.
- **Kept** 12 months after the matter is closed, then deleted by hand in the admin UI (privacy policy, docs/PRIVACY.md).
- The hub serves the pages (`webauth/legal.py`, `web/legal/kontakt.html`, `contact.html`, `contact.js`), only while
  the privacy policy in the same language is published.

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

A token stays valid until it expires (30 days, migration `1792774800_login_30_days.js`; the iPhone app renews it at
every launch) even if the account is un-approved meanwhile, so a
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

## Phone lost or token leaked

Change the Empire password (admin UI or "forgot password"): PocketBase then rejects every existing token, so the
phone, the website session and any copied token stop working. There is no per-device logout yet.
