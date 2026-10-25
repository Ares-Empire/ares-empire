# Privacy — what personal data the Empire handles

**Written 2026-10-24** (brief E6) from the code of every repo, for the privacy policy
(`www.ares-empire.de/datenschutz`, `/privacy`), the imprint (`/impressum`, `/imprint`) and Apple's privacy answers
(`empire-ios/docs/APP-STORE.md`). Keep it current: a service that starts storing or sending something new updates its
row here, then the pages (`web/legal/`), then the app's `PrivacyInfo.xcprivacy`.

Facts the code cannot show (server settings, providers) were confirmed by the lead on 2026-10-24/25; the AVV with
netcup was concluded by Patrik on 2026-10-25. The pages went live on 2026-10-25 after Patrik read them. A page is not
served while it contains `[lead to confirm]` or `[ADDRESS]` (`webauth/legal.py`): keep that marker for anything unconfirmed.

## What the public pages cover (Patrik, 2026-10-25)

This file is the full internal inventory. The public policy covers only processing that concerns people other than
Patrik, as a normal, neutral German policy (statements and "Sie", no "ich"/"du"; English the same with "you"):
visiting the websites (server logs), Empire accounts (sign-up, approval,
emails, login notices, logs), the website contact form, and in the apps only login, contact & support and push
registration; recipients, third-country transfers, storage periods, rights, BayLDA. Provinces that hold only Patrik's
data (Aresium, Arestemis, Aresus, Arestoteles, Aresync; checked 2026-10-25: the account server has only Patrik's two
accounts with a province service) are documented below and named nowhere in the public pages.

**Rule:** when a province is opened to other accounts (its service given to anyone but Patrik, or `open` in the hub
catalog), its section is added to the public policy, in German and English, **before** that happens; if it brings a new
kind of data (beyond the categories below), the AV contract with netcup is updated too (customer panel → Stammdaten →
AV-Vertrag).

## Facts that hold everywhere

- **Controller:** Patrik Breeck, REDACTED-ADDRESS, 85748 Garching, `REDACTED-EMAIL`. A private project, no company; no data
  protection officer needed (§ 38 BDSG: fewer than 20 people process data). Patrik chose the address (2026-10-25); the
  public pages show it only in the policy's controller line and the imprint.
- **Supervisory authority:** Bayerisches Landesamt für Datenschutzaufsicht (BayLDA), Promenade 18, 91522 Ansbach,
  www.lda.bayern.de (checked 2026-10-24).
- **Host:** one netcup VPS in Germany runs every service below (lead, 2026-10-24); Caddy in front, TLS everywhere.
  Processing agreement (AVV) with netcup concluded in the customer panel (Patrik, 2026-10-25). Declared there: affected persons: Interessenten (contact and support messages), visitors of the
  websites, users of the websites and apps (registered accounts); data: Personenstammdaten (name, optional; email),
  Kommunikationsdaten (email, messages), access and usage data (login data, IP addresses, server logs, push device
  ids), content data of the applications (settings, search profiles, notes); no special categories (Art. 9). No bank,
  payment or financial data: Aresium for other people keeps its data on their iPhone (decided 2026-10-25), and
  Patrik's own Aresium data on the server is his private data, not processed for anyone else. No device location.
- **DNS:** Hetzner (lead). Hetzner answers name lookups for our domains; it receives no account data.
- **No tracking** in the apps: no analytics, ads, crash-reporting or other third-party SDKs (lead; the Xcode projects
  have no packages). The websites set one cookie, the login (`empire_session`), and nothing for analytics.
- **Logins:** PocketBase tokens last 30 days (`1792774800_login_30_days.js`). Website: the `empire_session` cookie
  (HttpOnly, Secure, SameSite=Lax). Apps: one Keychain item shared by the Empire apps, readable only while the phone
  is unlocked, never synced off the device (`kSecAttrAccessibleWhenUnlockedThisDeviceOnly`). Services keep a 60 s
  cache keyed by the token's SHA-256, never the token.

## Per service

### Accounts (PocketBase, `auth.ares-empire.de`, `empire-accounts.service`)

| | |
|---|---|
| **Data** | Email, password (PocketBase stores only a hash), `name` (optional; the apps' sign-up asks for it, the website's does not), `verified`, `approved`, `services`, `requested` (the apps an account asked for and does not have yet), `language` (`en`/`de`, for later emails), `admin`, `ring` (the provinces in the hub's ring), created/updated. |
| **Where** | `/var/lib/empire-accounts/pb_data` (SQLite). |
| **How long** | Until the account is deleted. Unapproved sign-ups stay until Patrik approves or deletes them (no automatic clean-up). |
| **Emails** (Resend) | Confirmation link, password reset, "login from a new location" alert (PocketBase built-in), "approved" mail to the person; to the superusers an approval request naming the new account's email (`pb_hooks/accounts.pb.js`). |
| **Logs** | PocketBase's request log, with the visitor's IP (Caddy's `X-Forwarded-For`, `trustedProxy` in the first migration). Settings → Logs on the server (lead, 2026-10-24): `maxDays` 5, `logIP` true, `logAuthId` false, so 5 days, with IP, without the account. |
| **New-location alerts** | `_authOrigins` rows: `collectionRef`, `recordRef` (the account), `fingerprint`, `created`, `updated`. PocketBase 0.40.6 (`apis/record_helpers.go`, `authAlert`): `fingerprint = MD5(ip + userAgent)`, the user agent cut to 200 characters; no plain IP is stored. Made or refreshed at each login (password, OTP, OAuth2; not at a token refresh); at most 5 per account (`maxAuthOrigins`, the oldest go); deleted when the password changes or the account is deleted (`core/auth_origin_model.go`). A login with a new fingerprint (not the first login) emails the person the time, IP and user agent. |
| **Admins** | See the email, name, creation time and requested apps of accounts waiting for approval and of approved accounts that asked for another app, to decide them (`admin-visibility.pb.js`, hub `GET /api/empire/approvals`). |
| **Basis** | Account and login: Art. 6(1)(b) GDPR. Logs, rate limits, alerts: Art. 6(1)(f) (security). |
| **Deleting** | Every app: Settings → Account → Delete Ares account (since 2026-10-25); it reaches every service with per-account data (`deletions` jobs). An admin account cannot be deleted this way. |

### Hub (`www.ares-empire.de`, `webauth/server.py`)

- Login, sign-up and reset forms pass email and password to PocketBase on localhost with the visitor's IP (for
  PocketBase's rate limit). The hub stores nothing itself.
- Its log lines (journald) hold the request line and Caddy's address, **not** the visitor's IP (`address_string()`
  is the proxy).
- `GET /api/empire` (website and Empire app): asks Aresium's `/api/pulse` and Aresus's overview with the visitor's
  token for the live lines, cached 60 s per account in memory.
- **No third parties in the browser** (since 2026-10-25): the fonts (`web/fonts/`, `fonts.css`) and the scripts
  (React, Babel, Lucide in `web/vendor/`, byte-identical to unpkg, hashes in its README) are served by the hub itself;
  the same on aresium.de and arestoteles.de. Before that, every visitor's browser sent its IP to Google Fonts and
  unpkg (German courts ruled against Google Fonts loaded this way, LG München I, 3 O 17493/20). A new page or site
  loads nothing from another host (`webauth/test_server.py` checks the hub's pages).

### Push service (`empire-push.service`, `push/`)

| | |
|---|---|
| **Data** | Per device: app (bundle id), APNs device token, account id, `sandbox`/`production`, language, created/updated (`push/store.py`). Outbox: the last 200 notifications (time, app, account id or "all", title, body, link, language, result), never a device token. |
| **Where** | `/var/lib/empire-push/push.db`. |
| **How long** | Device: until logout, losing the app's service, Apple calling the token stale, or 60 days without re-registration (daily clean-up). Outbox: last 200 rows. |
| **Recipient** | Apple Push Notification service (title, body, link of each notification, the device token) once the APNs key exists; until then a dry run that sends nothing. Apple: for the EU, Apple Distribution International Ltd. (Ireland); its privacy policy says transfers from the EU to the US run under Standard Contractual Clauses (checked 2026-10-24; Apple was not found on the DPF list, whose search needs JavaScript). |
| **Logs** | Device tokens only as their first 6 characters; no visitor IP (proxy address). |
| **Basis** | Art. 6(1)(b); the iOS permission decides whether the phone shows them. |

### Arestemis (`arestemis.service`, `~/Arestemis`)

| | |
|---|---|
| **Data** | Per account: the hunt (search: kinds, people, places, areas, sizes, rents, move-in dates, sublets, portals, the free "extras" text), active/paused and times; settings (`application_mode`, `own_text` ≤ 5000 chars, `about_me` ≤ 2000 chars, notification switches); matches (listing, state new/saved/applied/dismissed, the AI's reason and warnings, the contact name from the listing, the application text and how it was made); filtered-out listings with reasons. Listings themselves are public portal data (title, rent, size, address or district, description, photo link) and can name a landlord or flatmate. |
| **"About you"** | Free text the AI uses ("22, Informatics at TUM, non-smoker"). The app's caption suggests gender and age (STATUS.md 05:27, because listings restrict on them). Nothing in it is required. |
| **Where** | `data/arestemis.db` in `/root/Arestemis`. |
| **How long** | Hunt, matches, rejected and seen rows: deleted with the hunt (`DELETE /hunts/{id}`, cascade). Rejected: 7 days. Listings no match needs: 30 days. Seen listing ids: 180 days. Settings: no delete route; they stay until the account is deleted, which today Patrik does by hand on request (the policy promises it; to-do below). |
| **Groq** (Groq, Inc., USA) | Each listing that passes the exact checks: the search, `about_me`, the listing (`llm/provider.py` `verify_messages`). AI applications: the listing, `own_text`, `about_me`, the contact name. "Describe it": the sentence typed (not stored by Arestemis). Groq is not certified under the DPF; the safeguard is the Standard Contractual Clauses in Groq's customer data processing addendum, part of its terms (lead, 2026-10-24). The policy names no Groq retention period: Groq processes the data only to give the answer, under that addendum. |
| **Telegram** | Only for the account in `TELEGRAM_FALLBACK_USER` (Patrik): a copy of each new match to his own chat, until push works. No other account's data. |
| **Portals** | The server reads WG-Gesucht, Kleinanzeigen, Immowelt (no user data sent). On the phone, listing photos load straight from the portal's image server (`AsyncImage(image_url)`), so the portal sees the phone's IP; "Open listing" opens the portal page. |
| **Logs** | uvicorn's access log (journald) with the visitor's IP (uvicorn trusts `X-Forwarded-For` from 127.0.0.1 by default), method, path and status; the query string (`?q=` of the place search) is dropped since 2026-10-25 (`main.py`, `_NoQueryInAccessLog`). Journald keeps 14 days since 2026-10-25 (`deploy/journald/retention.conf`). |
| **Basis** | Art. 6(1)(b) (the AI check and applications are the service asked for). |

### Aresus (`aresus.service`, `~/aresus`) and Aresync

| | |
|---|---|
| **Data** | About Patrik's server and machines, not about app users: check results, incidents (30 days after resolved), uptime per day (14 days), server vitals, last deploy per repo (commit hash, subject, date), Aresync run reports per machine (machine name, OS, times, counts, log lines with repo names and commits, problems, alerts; 30 days). Machine tokens only as SHA-256. |
| **Users** | Accounts with the `aresus` service (Patrik decides). Their account and push data are covered above. |
| **Telegram** | Aresync's own alerts go to Patrik's chat until push works (`TG_*` in each Aresync config). |
| **Logs** | uvicorn access log with IP, without the query string, as Arestemis. |

### Aresium (`aresium.service`, `aresium.de`, `~/aresium`)

- Patrik's own bank (VR Bank CAMT/CSV) and PayPal transactions: date, amount, balance, description, counterparty
  (names of people and shops), category, city/country, trip, the raw export row; categories, rules, corrections.
  Postgres in `aresium-db-1`. Imports through the app or website are parsed and not kept as files.
- **Only Patrik:** `EMPIRE_ALLOWED_USERS` lets in only listed account ids, even with the `aresium` service.
- Manual scripts only (`npm run ai`, `npm run places`, not the import route): transactions (description,
  counterparty, amount, date, place) to Groq for categories; merchant name + city to OpenStreetMap Nominatim.
- Telegram bot and reminders (`src/bot/`) talk only to Patrik's chat (`TELEGRAM_CHAT_ID`).
- Personal use by one person (Art. 2(2)(c) GDPR); listed in the policy so nobody wonders. Becomes a full section
  once Aresium is multi-user (EMPIRE.md → Open 5).

### Arestoteles (`arestoteles.service`, `~/Arestoteles`; vault `carlsenares/opinions`)

- Patrik's Weltbild vault (his notes, including political views). The `arestoteles` service gives access to his
  vault and is given only to Patrik and the test account (ARESTOTELES-APP.md).
- Edits from the app are committed as "Patrik Breeck (Arestoteles app)" and pushed to GitHub (GitHub, Inc., USA;
  private repo). GitHub is an active EU–US DPF participant (dataprivacyframework.gov participant 6174, next
  certification due 2027-08-03; checked 2026-10-24).
- Search (`GET /search?q=`) runs on our server (local model, brief E3); the query is not stored (uvicorn's access log
  drops the query string since 2026-10-25).
- On the phone: the vault copy and unsent quick notes in Application Support (file protection), the notes in
  Spotlight (on the device); all deleted at logout.
- Discuss: copies a prompt to the clipboard and opens `claude.ai/code`, only when tapped; Anthropic then gets what
  the user pastes, under their own Claude account.
- The website arestoteles.de keeps its own single password (Patrik only) and, like the hub, serves its fonts and
  scripts itself.

### Contact & support in the apps (brief E5)

- Collection `feedback` on the account server: account (deleted with the account), app, kind, message (≤ 5000),
  app version, system ("iOS 27.0 · iPhone"), language, created. Superusers only can read it.
- A hook mails each message through Resend to `REDACTED-EMAIL`, Reply-To the account's email. The mailbox is at
  IONOS SE, Germany (MX `mx00`/`mx01.ionos.de`; lead, 2026-10-24).
- Kept 12 months after the matter is closed (in the collection and the mailbox), earlier with the account.
- Basis: Art. 6(1)(b) for questions about the service, otherwise 6(1)(f).

### Website contact form (brief E7, `/kontakt`, `/contact`)

- Anyone, no account. The page (served by the hub, `web/legal/kontakt.html`, `contact.html`) posts from the browser
  straight to the account server's `contact` collection: name (optional, ≤ 100), email, message (≤ 5000), the page's
  language, and the honeypot `website` (always empty from people), created. Superusers only can read it. The page
  loads nothing from other hosts; it is served only while the privacy policy in its language is.
- A hook mails each message through Resend to `REDACTED-EMAIL` (IONOS), Reply-To the given address.
- IP address: in the account server's request log for 5 days (as every request), and in PocketBase's in-memory rate
  limiter (5 per hour per address); not stored with the message.
- Kept 12 months after the matter is closed (in the collection and the mailbox), deleted by hand in the admin UI.
- Basis: Art. 6(1)(f) (answering enquiries).

### Resend (email)

Resend, Inc., USA: sends every email above from `noreply@ares-empire.de` (`smtp.resend.com:2465`), from AWS
`us-east-1` (the domain's SPF addresses; lead, 2026-10-24). Resend is certified under the EU–US Data Privacy
Framework; its DPA also has the SCCs; stored data (sent-mail logs) is in the US (Resend's GDPR page, 2026-10-24).

### Backups and copies

- **Nightly backup** since 2026-10-25 ([BACKUP.md](BACKUP.md)): every service's data that cannot be rebuilt
  (accounts, Arestemis, Aresus, push, Aresium, the hub's data, the `.env` files). Kept 7 days on the server (plain,
  root only) and up to about 6 months on Patrik's MacBook (encrypted with age; only the Mac has the key). No new
  provider: the server copies are covered by the netcup AVV, the Mac is the controller's own device. Data deleted
  in a service leaves the backups when their copies expire (at most about 6 months).
- The one-off copies made during the builds of 2026-10-24/25 (`pb_data.before-*`, `/root/arestemis-backup-*`,
  `/root/backups/`, `state.json.bak-*`) were deleted on 2026-10-25. A copy made before a migration is deleted once the
  migration is checked live.

## Published

2026-10-25: Patrik approved the text, the AVV with netcup is concluded, journald keeps 14 days
(`deploy/journald/retention.conf`), the address is filled in (his choice), the imprint's second contact route is the
contact form.

## To do (follow-up builds)

1. ~~**Delete your account** in every app.~~ Done 2026-10-25 (briefs F1/F2): every app creates, leaves and deletes the
   account (Settings → Account); deleting reaches every service with per-account data (`deletions` jobs: Arestemis,
   push); leaving an app deletes its server data first (`DELETE /api/arestemis/me`). The website has no delete button
   yet (the policy names the apps and email). The optional name is now also asked at sign-up in the apps.
2. ~~**Self-host the website fonts and scripts.**~~ Done 2026-10-25: hub, aresium.de and arestoteles.de serve them
   themselves; the policy's "Externe Inhalte" / "External content" section and the Google/unpkg lines are gone (the
   sections after it moved up by one).
3. ~~**Search terms in logs.**~~ Done 2026-10-25: Arestemis and Arestoteles drop the query string from uvicorn's
   access log (path, status and IP stay, 14 days).
4. **Links:** the login pages and the apps' Settings link to the privacy policy and imprint; the signed-in hub,
   aresium.de and arestoteles.de do not yet (a footer link, before other people use them).
5. ~~**Backups.**~~ Done 2026-10-25: the one-off copies are deleted, the nightly backup runs ([BACKUP.md](BACKUP.md)),
   and the policy's section 9 (Speicherdauer / Storage period) names it and its periods (Patrik approved the text
   2026-10-25).
