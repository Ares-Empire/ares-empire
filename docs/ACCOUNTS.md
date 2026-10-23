# Empire accounts — one login for every service

**Planned 2026-10-23.** Status: not built yet. Replaces the "Empire SSO" expansion.

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

## Open questions (decide when building)

- Where the account database lives: a small Postgres or SQLite next to `webauth/server.py`.
- Which email service sends password resets.
- For multi-user Aresium: which data is per person (transactions, accounts, rules) and
  which is shared (the category list).
