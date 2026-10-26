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
- Data: `/var/lib/empire-accounts/pb_data` (not in git). In the nightly backup ([BACKUP.md](BACKUP.md)).
- **Users** (`users` collection): email + password, plus
  - `approved` — set by a superuser or an admin approving another account; login needs
    `verified = true && approved = true`.
  - `services` — which provinces the account may use (`empire`, `aresium`, `arestemis`, `aresus`, `arestoteles`; add
    more in a new migration, to both `services` and `requested`).
  - `requested` and `language` — the apps the account asked for, and the language of its emails
    ([Accounts in every app](#accounts-in-every-app)).
  - `admin` — only a superuser may set this, including at sign-up.
  - (`ring`, the saved hub ring of 2026-10-24, was dropped on 2026-10-25 with what it held, migration
    `1793400000_drop_ring.js`: the hub's ring is the account's `services`.)
  - Normal users can rename themselves, change password, set `requested` and `language`, and delete their account.
    They can't touch `approved`/`services`/`verified`/`admin`, and can only see their own record. A sign-up cannot
    choose its record id.
  - Admins can list/view all accounts, update only `approved`, `services` and `requested` on other accounts, and
    delete unapproved accounts. An admin cannot delete an approved account, including their own (deleting their own
    answers 403 with a sentence that says why, below).
    The `admin-visibility.pb.js` hook exposes account emails to admins for approvals without granting
    PocketBase's broader `manageRule` privileges.

Local verification (no live account data): `bash accounts/test-rules.sh` uses a disposable PocketBase 0.40.6
from `$POCKETBASE` (default `~/.pocketbase-test/pocketbase`) and checks API rules, email visibility, feedback, the
contact form, the account emails and notifications, the leave route, the deletion jobs and migration rollback/reapply. It loads every hook; their mail goes to a local SMTP
sink the script starts (never Resend, never the system's sendmail) and the deletion calls and notifications to a fake
service on localhost, which records each notification's body for the checks. Hub contract tests use fake PocketBase responses: `python3 -m unittest webauth/test_server.py`.
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
- **Email:** after each create the hook mails it to `REDACTED-EMAIL` (`SUPPORT_TO` in `pb_hooks/lib/mail.js`,
  shared with the contact hook) from the server's sender, `Reply-To` the account's email, subject
  `[Arestoteles] Idea: <first words>`, a plain body (kind, app, version, system, language, account email, the
  message, a link to the record). A failed email is logged
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
- **Email:** after each create the hook mails it to Patrik (`SUPPORT_TO`, `pb_hooks/lib/mail.js`) from the server's sender, `Reply-To`
  the given address, subject `[Website] Kontakt: <first words>` (German page) or `[Website] Contact: …`, a plain body
  (name, email, language, the message, a link to the record). A failed email is logged (`contact email failed`) and
  the record stays.
- **Kept** 12 months after the matter is closed, then deleted by hand in the admin UI (privacy policy, docs/PRIVACY.md).
- The hub serves the pages (`webauth/legal.py`, `web/legal/kontakt.html`, `contact.html`, `contact.js`), only while
  the privacy policy in the same language is published.

## Accounts in every app (2026-10-25)

Patrik (2026-10-25): one central Ares account, creatable and controllable from every app (the first app someone gets
may not be the Empire app, the least useful one for most people), and every app independently controllable: in each
app's settings you can delete that app's data and access, or your whole Ares account. **One account, one password**
for every app (separate accounts per app were rejected: every sign-up, approval, reset and deletion would multiply,
and the shared login on one iPhone would break). Contract: `empire-ios/docs/build-2026-10-25/briefs/F-accounts-contract.md`.

### What every app can do

| Action | Server |
|---|---|
| Create an account | `POST /api/collections/users/records` `{email, password, passwordConfirm, name?, requested: [<this app's service>], language: "en" \| "de"}`, then `POST /api/collections/users/request-verification` `{email}` |
| Forgot password | `POST /api/collections/users/request-password-reset` `{email}` (always 204) |
| Ask for access (logged in, the account lacks the service) | `PATCH /api/collections/users/records/<id>` `{requested: <current requested + this service>}` |
| Change password | `PATCH /api/collections/users/records/<id>` `{oldPassword, password, passwordConfirm}`; old tokens end, the app logs in again with the new password |
| Leave this app (its access and its data) | 1. `DELETE /api/<service>/me` where the service keeps data per account (today Arestemis); 2. `POST https://auth.ares-empire.de/api/empire/leave` `{service}` → `{services, requested}` |
| Delete the whole account | the app checks the password (`auth-with-password`), then `DELETE /api/collections/users/records/<id>` → 204; the server deletes the account's data in every service (below) |

Login still needs `verified && approved`. An app cannot tell "wrong password" from "not approved yet", so its login
error says both.

### The account record

- **`requested`** (multi-select, the values of `services`): the apps the account asked for and does not have yet.
  The account sets it (sign-up and update); admins may change it on other accounts (the hub's approve and decline).
  Every save drops from `requested` what is already in `services` (migration `1793300000_requested_language.js`,
  hook `pb_hooks/accounts.pb.js`).
- **`language`** (`en`, `de`): the language of the emails the account gets later. Set by the account (sign-up,
  settings); admins cannot change it. Empty counts as English.
- **Approval grants what was asked:** when `approved` switches on (admin UI, the hub, any save), the account gets
  `services ∪ requested`. For an approved account, granting a request means putting the service into `services`
  (admin UI: add it there; it leaves `requested` by itself). Declining: an unapproved account is deleted (as before);
  an approved account's request is removed from `requested`, the account stays.
- Accounts waiting for approval from before 2026-10-25 (no services) were given `requested: [empire]`: they signed up
  on the website.
- **A sign-up cannot choose its record id** (`@request.body.id:isset = false` in the create rule): the id is the key
  of an account's data in every service, so the id of a deleted account must never come back to a new one.
- **`POST /api/empire/leave`** `{service}` (custom route in `pb_hooks/accounts.pb.js`): needs a users login (a
  superuser token answers 403, none 401); removes the service from the account's `services` and `requested` and
  answers `200 {services, requested}`; an unknown or missing service is `400`. Leaving an app the account does not
  have changes nothing. It sends no email.
- **The administrator cannot leave an app or delete his account from an app** (2026-10-25): only an admin gives
  access and an admin cannot change his own `services`, so Patrik could lock himself out of the hub from the phone.
  The leave route answers an admin account `403`, and so does `DELETE /api/collections/users/records/<own id>` with an
  admin's login (a router middleware in `accounts.pb.js` answers before the delete rule, which refuses it anyway but
  only with PocketBase's generic 404). Both in PocketBase's error shape, the sentence in the request's language
  (`Accept-Language`, the hub's rule): `{"status": 403, "message": "This is the administrator account; it cannot
  leave an app or be deleted here.", "data": {}}`, German "Das ist das Administratorkonto. Es kann hier keine App
  verlassen und nicht gelöscht werden." The route's other sentences are translated the same way (`ANSWERS` in
  `pb_hooks/lib/accounts.js`).

### Emails

| When | To | Language |
|---|---|---|
| Someone signs up (not a superuser in the admin UI) | Patrik: every superuser not at example.com | English: email, name, the apps asked for, the language, a link to the account in the admin UI |
| An approved account asks for more apps | Patrik | English: the new apps, what it has, everything it asked for, its language, the link |
| Approved for the first time, or given more apps | the account | its `language`: which apps, how to log in (and the hub's address when `empire` is among them) |
| Confirm the email address, reset the password (PocketBase's own) | the account | English and German in one message (migration `1793300200_emails_de_en.js`) |
| A deletion job still fails a day after the deletion | Patrik | English, once per job |

The texts are in `pb_hooks/lib/mail.js`, the one mail module of every hook. "Patrik" here means the superusers
(`superusers()`: whoever can approve in the admin UI), not `SUPPORT_TO`, the address for what people write to him
(feedback, the contact form). A failed email is logged (`approval request email failed`, `access request
email failed`, `approved email failed`, `account deletion alert email failed`) and never fails the request.

### Notifications (2026-10-25)

Next to three of the emails, `pb_hooks/accounts.pb.js` sends a notification to the Empire app through the push service
(`pb_hooks/lib/push.js`, `POST http://127.0.0.1:8096/send`, 3 s timeout; the texts and fields:
[PUSH.md → Who sends what](PUSH.md#who-sends-what)):

| When | To | Says |
|---|---|---|
| Approved for the first time, or given more apps | the account | "<apps> is/are ready", "Open the Empire app to start." |

English with German in `localized.de` (the push service picks per device). Sign-ups and access requests reach Patrik
by email only, not as notifications (Patrik, 2026-10-26). A member never learns anything about another account. A notification that fails (the push service down, refusing, slow) is logged
(`push failed`, with the thread and the account id, never the texts) and never fails or undoes the request. Until
Apple's push key exists the push service runs as a dry run and only keeps them in its outbox.

### Deleting an account reaches every service

- After a `users` record is deleted (by the account itself, by an admin declining it, in the admin UI),
  `pb_hooks/deletions.pb.js` writes one job per service that keeps data per account into **`deletions`** (`account`,
  `service`, `attempts`, `done`, `last_error`, `reported`, `created`, `updated`; superusers only; migration
  `1793300100_deletions.js`). **CONTRACT ADDITION:** `reported` remembers that Patrik was mailed about the job.
- The cron **`empire-deletions`** (every 5 minutes; run by hand: admin UI → Settings → Crons) calls each open job,
  oldest first: `DELETE http://127.0.0.1:<port>/internal/accounts/<id>`. 2xx or 404 → `done`; anything else →
  `attempts + 1`, `last_error`, tried again on the next run. A service that does not answer at all is not called
  again in that run. A job still failing a day after the deletion is mailed to Patrik once.
- Today's services: **Arestemis** `127.0.0.1:8097` (settings, hunts, matches with their applications, rejected
  listings; [Arestemis API.md](https://github.com/Ares-Empire/Arestemis/blob/main/docs/API.md)) and the **push
  service** `127.0.0.1:8096` (devices of every app and outbox rows; [PUSH.md](PUSH.md)). `ARESTEMIS_INTERNAL_URL` and
  `PUSH_INTERNAL_URL` in PocketBase's environment override them (only the tests do). The account server's own
  `feedback` goes by cascade.
- Single-owner services (Aresium, Aresus, Arestoteles: only Patrik's data) have no deletion route; leaving them
  removes the access and the data on the phone only.
- **A new service with per-account data** needs: `DELETE /internal/accounts/<id>` on localhost, never routed by
  Caddy, `204` also when there is nothing (the account server takes a 404 as done, so deploy the service first);
  `DELETE /api/<service>/me` for "leave this app"; an entry in `pb_hooks/lib/deletions.js`; its value in the
  `service` field of `deletions` (a new migration).
- **A stuck job** (the email): fix the service, or delete the data by hand, then switch on `done` in the admin UI
  (Collections → deletions).

### The hub's approvals (website and Empire app)

`GET /api/empire/approvals` lists new sign-ups and approved accounts with open requests (filter
`approved = false || requested:length > 0`): `[{id, email, name, created, requested, approved, verified}]`
(`verified`: the email address is confirmed).
`POST /api/empire/approvals/<id>` `{approve: true}` sends `{approved: true, "services+": <the requests>}`;
`{decline: true}` deletes an unapproved account or sends `{"requested-": <the requests>}` for an approved one. "The
requests" are those the hub reads just before its write; when the app also sends `requested` (the apps the card
showed, 2026-10-25), only those of them. So a request made after Patrik looked stays waiting, and the `+`/`-` forms
keep one made between the hub's read and its write as well. A first approval grants everything left in `requested`
(the hook above), so for a sign-up the hub also sends `"requested-"` with the requests Patrik did not see. The answer
carries the fresh list, `{ok, approvals, pending}`. [API-EMPIRE.md](API-EMPIRE.md).

The hub's "+" (`POST /api/empire/request` `{service}`, 2026-10-25) asks for an app the same way an app does, with the
account's own token: it reads the account (`fields=id,services,requested`) and sends `{"requested+": [service]}`; only
apps `open` in the hub's catalog. The hooks above then mail and notify Patrik.

## Website flow

- `/login` → *Log in* button + "New account? Sign up". `/login/email` → email + password.
- `/signup` (hub only) creates the account asking for `empire`, in English, and sends the confirmation email. A
  hook (`accounts/pb_hooks/accounts.pb.js`) emails the superusers an approval request with a direct link,
  and emails the person once `approved` is switched on ([Accounts in every app](#accounts-in-every-app)).
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
`EMPIRE_ALLOWED_USERS` while Aresium holds only one person's data). Aresus and Arestoteles do the same since
2026-10-25: they hold only Patrik's data and are never opened to others, while any account can ask for their service
and an approval grants it. Empty or unset means nobody gets in; others get the same 403 as "no access".

## Open questions (decide when building)

- Settled 2026-10-25: other people's Aresium data (transactions, accounts, rules, categories) stays on their iPhone,
  not on the server (EMPIRE.md → Now and next).

## Phone lost or token leaked

Change the Empire password (admin UI or "forgot password"): PocketBase then rejects every existing token, so the
phone, the website session and any copied token stop working. There is no per-device logout yet.
