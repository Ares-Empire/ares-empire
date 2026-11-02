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
Patrik, as a normal, neutral German policy: impersonal statements ("Daten werden gespeichert", "die App fragt ab"), as few pronouns as possible, no "ich"/"du"; "Sie" only where the reader has to act, as in the rights section (Patrik, 2026-10-27); English the same:
visiting the websites (server logs), Empire accounts (sign-up, approval,
emails, login notices, logs), the website contact form, and in the apps only login, contact & support and push
registration; recipients, third-country transfers, storage periods, rights, BayLDA. Provinces that hold only Patrik's
data (Arestemis, Aresus, Arestoteles, Aresync; checked 2026-10-25: the account server has only Patrik's two accounts
with a province service) are documented below and named nowhere in the public pages. Aresium is named for other
people's use (phone mode, section 6 → "Aresium"); Patrik's own server data stays out of the public pages.

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
| **Data** | Email, password (PocketBase stores only a hash), `name` (optional; the apps' sign-up asks for it, the website's does not), `verified`, `approved`, `services`, `requested` (the apps an account asked for and does not have yet), `language` (`en`/`de`, for later emails), `admin`, created/updated. The saved hub ring (`ring`) was dropped on 2026-10-25 with what it held (migration `1793400000_drop_ring.js`): the ring is now the account's `services`. |
| **Where** | `/var/lib/empire-accounts/pb_data` (SQLite). |
| **How long** | Until the account is deleted. Unapproved sign-ups stay until Patrik approves or deletes them (no automatic clean-up). |
| **Emails** (Resend) | Confirmation link, password reset, "login from a new location" alert (PocketBase built-in), "approved" mail to the person; to the superusers an approval request naming the new account's email (`pb_hooks/accounts.pb.js`). |
| **Notifications** (push service, since 2026-10-25) | To the account itself: that its apps are ready (none to Patrik about other accounts: he gets sign-ups and requests by email, 2026-10-26) (`pb_hooks/lib/push.js`). Through Apple once the APNs key exists (push service below). |
| **Logs** | PocketBase's request log, with the visitor's IP (Caddy's `X-Forwarded-For`, `trustedProxy` in the first migration). Settings → Logs on the server (lead, 2026-10-24): `maxDays` 5, `logIP` true, `logAuthId` false, so 5 days, with IP, without the account. |
| **New-location alerts** | `_authOrigins` rows: `collectionRef`, `recordRef` (the account), `fingerprint`, `created`, `updated`. PocketBase 0.40.6 (`apis/record_helpers.go`, `authAlert`): `fingerprint = MD5(ip + userAgent)`, the user agent cut to 200 characters; no plain IP is stored. Made or refreshed at each login (password, OTP, OAuth2; not at a token refresh); at most 5 per account (`maxAuthOrigins`, the oldest go); deleted when the password changes or the account is deleted (`core/auth_origin_model.go`). A login with a new fingerprint (not the first login) emails the person the time, IP and user agent. |
| **Admins** | See the email, name, creation time, requested apps and whether the email is confirmed of accounts waiting for approval and of approved accounts that asked for another app, to decide them (`admin-visibility.pb.js`, hub `GET /api/empire/approvals`). |
| **Basis** | Account and login: Art. 6(1)(b) GDPR. Logs, rate limits, alerts: Art. 6(1)(f) (security). |
| **Deleting** | Every app: Settings → Account → Delete Ares account (since 2026-10-25); it reaches every service with per-account data (`deletions` jobs). An admin account cannot be deleted this way. |

### Hub (`www.ares-empire.de`, `webauth/server.py`)

- Login, sign-up and reset forms pass email and password to PocketBase on localhost with the visitor's IP (for
  PocketBase's rate limit). The hub stores nothing itself.
- Its log lines (journald) hold the request line and Caddy's address, **not** the visitor's IP (`address_string()`
  is the proxy). Since 2026-10-25 also: the traceback of an unexpected API error (method and path; no IP, token or
  body), and short notes when `state.json` entries are skipped or the pending count is unavailable.
- `GET /api/empire` (website and Empire app): asks Aresium's `/api/pulse` and Aresus's overview with the visitor's
  token for the live lines, cached 60 s per account in memory, only for the provinces the account has.
- `POST /api/empire/request` (the "+", 2026-10-25): writes the account's own `requested` on the account server with
  the account's token; the hub keeps nothing.
- **No third parties in the browser** (since 2026-10-25): the fonts (`web/fonts/`, `fonts.css`) and the scripts
  (React, Babel, Lucide in `web/vendor/`, byte-identical to unpkg, hashes in its README) are served by the hub itself;
  the same on aresium.de and arestoteles.de. Before that, every visitor's browser sent its IP to Google Fonts and
  unpkg (German courts ruled against Google Fonts loaded this way, LG München I, 3 O 17493/20). A new page or site
  loads nothing from another host (`webauth/test_server.py` checks the hub's pages).

### Push service (`empire-push.service`, `push/`)

| | |
|---|---|
| **Data** | Per device: app (bundle id), APNs device token, account id, `sandbox`/`production`, language, created/updated (`push/store.py`). Outbox: the last 200 notifications (time, app, account id or "all", title, body, link, language, result), never a device token. Aresus addresses its pushes to the owner's account id (since 2026-10-25), not "all". The account server's notifications go only to an account about itself ("… is ready"); none tell anyone about another account (2026-10-26). |
| **Where** | `/var/lib/empire-push/push.db`. |
| **How long** | Device: until logout, losing the app's service, Apple calling the token stale, or 60 days without re-registration (daily clean-up). Outbox: last 200 rows. |
| **Recipient** | Apple Push Notification service (title, body, link of each notification, the device token) once the APNs key exists; until then a dry run that sends nothing. Apple: for the EU, Apple Distribution International Ltd. (Ireland); its privacy policy says transfers from the EU to the US run under Standard Contractual Clauses (checked 2026-10-24; Apple was not found on the DPF list, whose search needs JavaScript). |
| **Logs** | Device tokens only as their first 6 characters; no visitor IP (proxy address). |
| **Basis** | Art. 6(1)(b); the iOS permission decides whether the phone shows them. |

### Arestemis (`arestemis.service`, `~/Arestemis`)

| | |
|---|---|
| **Data** | Per account: hunts (since 2026-11-01 several, up to 30, each with an optional name; a flat search: kinds, people, places, areas, sizes, rents, move-in dates, sublets, portals, the free "extras" text; a thing search (brief 116): the search words, words to leave out, price range and VB allowance, condition, pickup places and radius or shipping, private sellers only, sites, the extras text), active/paused and times; settings (`application_mode`, `own_text` ≤ 5000 chars, `about_me` ≤ 2000 chars, notification switches); matches (listing, state new/saved/applied/dismissed, the AI's reason and warnings, the contact name from a flat listing, the application text and how it was made, whether it was found when the hunt started, how far a VB price lies over the maximum); filtered-out listings with reasons. Listings themselves are public portal data (title, rent or price, size or condition, address, district or place and distance, description, photo link); a flat listing can name a landlord or flatmate. **For things no seller name is stored** (brief 116: `contact` stays empty, the facts hold only the listing's attributes). |
| **"About you"** | Free text the AI uses ("22, Informatics at TUM, non-smoker"). The app's caption suggests gender and age (STATUS.md 05:27, because listings restrict on them). Nothing in it is required. |
| **Where** | `data/arestemis.db` in `/root/Arestemis`. |
| **How long** | Hunt, matches, rejected and seen rows: deleted with the hunt (`DELETE /hunts/{id}`, cascade). Rejected: 7 days. Listings no match needs: 30 days. Seen listing ids: 180 days. Settings: no delete route; they stay until the account is deleted, which today Patrik does by hand on request (the policy promises it; to-do below). |
| **Groq** (Groq, Inc., USA) | Each flat listing that passes the exact checks: the search, `about_me`, the listing (`types/flat/prompts.py` `verify_messages`). Each thing listing that passes them: the thing search and the listing, **without `about_me`** (`types/item/prompts.py`). AI applications: the listing, `own_text`, `about_me`, the contact name. "Describe it": the sentence typed (not stored by Arestemis). Groq is not certified under the DPF; the safeguard is the Standard Contractual Clauses in Groq's customer data processing addendum, part of its terms (lead, 2026-10-24). The policy names no Groq retention period: Groq processes the data only to give the answer, under that addendum. |
| **Telegram** | Only for the account in `TELEGRAM_FALLBACK_USER` (Patrik): a copy of each new match to his own chat, until push works. No other account's data. |
| **Portals** | The server reads WG-Gesucht, Kleinanzeigen, Immowelt and ImmoScout24 (no user data sent). For a thing hunt it sends each chosen site the search as a search there would; no account or person is named anywhere. Kleinanzeigen (brief 116): the search words, the price range, the place and radius, private sellers or not, shipping or not. MTB-News Bikemarkt (brief 122): the search words, Germany-wide. mydealz (brief 120): nothing (one shared feed of all new deals, filtered on the server). eBay (brief 118, through eBay's official Browse API; keys since 2026-11-02, registered as storing no eBay user data): the search words, price, condition, and for pickup the town's postcode and radius. IKEA Preowned (brief 126, planned): the search words and the town's coordinates and radius. Vinted (briefs 127/128, planned): the search words, price and condition. On the phone, listing photos load straight from the portal's image server (`AsyncImage(image_url)`), so the portal sees the phone's IP; "Open listing" opens the portal page. |
| **Place coordinates** (OpenStreetMap Foundation, UK; Nominatim) | Approved by Patrik 2026-11-02 (brief 125). When a thing search is saved, the server looks up each of its places that has none yet: the town's name and federal state, from the server's address, with an Arestemis User-Agent; never while someone types, never for places used only by flat hunts. Kept: the town's coordinates and postcode, on the place record (towns are shared between accounts, not personal data). The UK has an adequacy decision; a town name identifies no one. Attribution "© OpenStreetMap contributors (ODbL)" in the app's Fonts & licences page. |
| **Proxy provider** | Some sites are read through a proxy provider. The connection is HTTPS through the proxy, so the provider sees which site the server connects to and how much data moves, not the search or the answers. |
| **Logs** | uvicorn's access log (journald) with the visitor's IP (uvicorn trusts `X-Forwarded-For` from 127.0.0.1 by default), method, path and status; the query string (`?q=` of the place search) is dropped since 2026-10-25 (`main.py`, `_NoQueryInAccessLog`). Journald keeps 14 days since 2026-10-25 (`deploy/journald/retention.conf`). |
| **Basis** | Art. 6(1)(b) (the AI check and applications are the service asked for). |

### Aresus (`aresus.service`, `~/aresus`) and Aresync

| | |
|---|---|
| **Data** | About Patrik's server and machines, not about app users: check results, incidents (30 days after resolved), uptime per day (14 days), server vitals, last deploy per repo (commit hash, subject, date), Aresync run reports per machine (machine name, OS, times, counts, log lines with repo names and commits, problems, alerts; 30 days). Machine tokens only as SHA-256. |
| **Users** | Accounts with the `aresus` service (Patrik decides). Their account and push data are covered above. |
| **Telegram** | None since 2026-11-01: Aresync's alerts reach Patrik as Aresus pushes (its Telegram copy retired). |
| **Logs** | uvicorn access log with IP, without the query string, as Arestemis. |

### Demo pages (`aresium.de/demo`, `www.ares-empire.de/demo`; Patrik, 2026-10-27)

- Public pages without an account that show a made-up sample (Aresium: `app/dashboard.sample.json`, a seeded generated
  account; the hub: `app/samples/empire.demo.json`, a made-up guest, `tools/empire_samples.py --web`). No real data,
  nothing entered is sent or stored: Aresium's demo answers its own API requests in the browser and refuses every
  change; the hub's demo runs its sample mode in memory. The real data and every API stay behind the login.
- Processing: only the request itself (IP address, time, URL), as for any page; neither server writes an access log
  (the hub's log lines carry Caddy's address, Aresium logs only errors), Caddy's error entries keep 14 days.
- The public policy covers them since 2026-10-27 (Patrik: aresium.de and every demo page): its first sentence names
  "the websites www.ares-empire.de and aresium.de, the demo pages of the Ares apps", section 2 says the demos show
  made-up data and store nothing. A new demo page fits that sentence as long as it, too, stores nothing; one that
  would store something gets its own section first.

### Aresium (`aresium.service`, `aresium.de`, `~/aresium`)

- Patrik's own bank (VR Bank CAMT/CSV) and PayPal transactions: date, amount, balance, description, counterparty
  (names of people and shops), category, city/country, trip, the raw export row; categories, rules, corrections.
  Postgres in `aresium-db-1`. Imports through the app or website are parsed and not kept as files.
- **Only Patrik:** `EMPIRE_ALLOWED_USERS` lets in only listed account ids, even with the `aresium` service.
- Manual scripts only (`npm run ai`, `npm run places`, not the import route): transactions (description,
  counterparty, amount, date, place) to Groq for categories; merchant name + city to OpenStreetMap Nominatim.
- Telegram bot and reminders (`src/bot/`) talk only to Patrik's chat (`TELEGRAM_CHAT_ID`).
- The above is Patrik's own data (server mode, the owner list): personal use by one person (Art. 2(2)(c) GDPR), not
  described in the public pages.
- **Everyone else: phone mode, no account** (built 2026-10-27, briefs 15, 18, 22; D7 in
  [ARESIUM-FOR-OTHERS.md](ARESIUM-FOR-OTHERS.md); `empire-ios/CLAUDE.md` → "Aresium phone mode"). Aresium opens without
  a login. The bank files and everything read from them (payments with the bank's original row, the other party's
  IBAN, balances), the chosen categories, learned rules and confirmed column layouts are read, sorted and stored on
  the iPhone: SwiftData, one store per iPhone (`Application Support/Aresium/local/`), file protection complete, not
  excluded from the person's device backups. Sorting uses the bundled shop list and the person's corrections; no AI,
  no network. Only when a login with the `aresium` service exists does the app ask `GET /api/mode` (the token checked
  with the account server; no cache entry, no log line); the server keeps nothing about anyone but Patrik.
- The data belongs to the iPhone, not to a login: logging in or out, leaving Aresium and deleting the Ares account
  never touch it. Deleted by Settings → "Delete Aresium data on this iPhone" (also any older per-account store left by
  the move-over), the lock's "Forgot the code?", removing the app. Widgets: the current month's totals in the App
  Group container, deleted with the data; with the lock on none are kept. Known gap: removing Aresium while other Ares
  apps stay leaves the widget totals in the App Group until the last Ares app goes. Export and restore: one JSON file
  through the share sheet; where it goes is the person's choice.
- The lock (optional): Face ID is checked by iOS (the app gets only the result); the own 6-digit code only as a salted
  PBKDF2 hash in Aresium's own Keychain item, this device only.
- Receipts (brief 31, 2026-10-28): photographed with the camera (VisionKit's document scanner) or picked from the
  photo library (PhotosPicker, no library permission); read on the iPhone with Vision (text and the register's QR
  code); the image is never written to disk and is released after reading. Stored in the same store: the read rows,
  shop, date, time, total, currency, card or cash, category, the joined payment. Nothing leaves the phone.
  `NSCameraUsageDescription` says what the camera is for.
- Contact & support without a login goes to the `contact` collection (as the website's form), with a footer naming
  the app, its version, iOS and the topic (the collection has fields for them since 2026-10-30, `app`, `app_version`,
  `system`, `kind`, which a later build can send instead; the account server reads the footer either way). Sharing a bank's format: "Bank formats shared from Aresium" below.
- Public policy: section 6 → "Aresium" (German and English). No change to the netcup AVV: no financial data of
  anyone but Patrik reaches the server.

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

### Website contact forms (brief E7, `/kontakt`, `/contact`; Aresium's own since 2026-10-30, the hub's two since 2026-11-01)

- Anyone, no account. Three pages, each also where people ask for its app: Aresium's (aresium.de/contact and /kontakt,
  `aresium` `src/web/contact-page.ts`) and on the hub the Ares Empire's (/contact and /kontakt, which replaced the hub's
  general form on 2026-11-01 and stays the Empire's general contact) and Arestemis's (/arestemis/contact and
  /arestemis/kontakt), both `webauth/contact.py`. They post from the browser straight to the account server's
  `contact` collection: name (optional, ≤ 100), email, message (≤ 5000; may be empty when asking for the app), the
  page's language, the app (`aresium`, `empire`, `arestemis`), the topic (`kind`: get the app, question, problem, idea,
  other), and the honeypot `website` (always empty from people), created. Superusers only can read it. The pages load
  nothing from other hosts; the hub's are served only while the privacy policy in their language is. A new form is
  covered by the policy's section 4 before it goes live (done for both on 2026-11-01, To do 8).
- The hub's two pages remember the look chosen with their header's switch (light; dark is the default) in the
  browser's `localStorage` (`ares-empire-appearance`), as aresium.de does with its own switch (`aresium-appearance`).
  It stays in the browser, is never sent, holds nothing about the person, and is set only when the visitor switches.
  Section 3 of the public policy names both since 2026-11-01 (a stored setting the visitor asked for, § 25(2) no. 2
  TDDDG; To do 8).
- Asking for an app: the email address is used to send the link for installing it (a TestFlight link Patrik sends
  himself). If Patrik instead invites people by email in App Store Connect, their address goes to Apple: the policy
  must name that first. Arestemis and the Ares Empire app also need an Ares account (created in the app; the policy's
  account section covers it). Arestemis itself is still named nowhere in the public pages: a request is only a contact
  message, but **giving the `arestemis` service to anyone but Patrik needs its section first** (the Rule above: the
  hunt, "About you", Groq in the USA, the portals).
- A hook mails each message through Resend to `REDACTED-EMAIL` (IONOS), Reply-To the given address.
- IP address: in the account server's request log for 5 days (as every request), and in PocketBase's in-memory rate
  limiter (5 per hour per address); not stored with the message.
- Kept 12 months after the matter is closed (in the collection and the mailbox), deleted by hand in the admin UI.
- Basis: Art. 6(1)(f) (answering enquiries).

### Bank formats shared from Aresium (brief 21, 2026-10-27)

- Anyone using Aresium, no account needed (the app sends no login). When Aresium does not know someone's bank, they can
  send the file's format so Claude can add the bank for everyone: the bank's name they type, the file's header names,
  which column means what, the separator, date and number style, the app's version and language, created. Never a
  payment, amount, IBAN, name or the account. Collection `bank_formats` on the account server; superusers only can
  read it ([ACCOUNTS.md](ACCOUNTS.md) → Bank formats shared from Aresium).
- No personal data in the record: the app refuses to send a format whose header or status words look like an IBAN or
  account number, an email address, a date, an amount or 5+ digits, and the server refuses the same again, also in the
  bank's name (`pb_hooks/lib/bank-formats.js`, `pb_hooks/lib/personal-data.js`). A person's name in a column's name cannot be detected; header cells are
  limited to 80 characters.
- A hook mails each format through Resend to `REDACTED-EMAIL` (IONOS), without a Reply-To.
- IP address: in the account server's request log for 5 days (as every request), and in PocketBase's in-memory rate
  limiter (5 per hour per address); not stored with the format.
- Kept until the bank is added to Aresium, at most 12 months; deleted by hand (the record in the admin UI and the
  email). The nightly backup keeps copies as for all account data (Backups below).
- Basis: Art. 6(1)(f) for the IP address in the logs and the rate limit (security); the format itself is no personal
  data. The public policy names it in its Aresium section before Aresium opens (To do 6).

### Bank requests from Aresium (brief 26, 2026-10-27)

- Anyone using Aresium, no account needed (the app sends no login). When their bank is not in Aresium's bank guide,
  they can send its name so Patrik knows which banks to add: the bank's name they type, the app's version and
  language (optional), created. No file, payment or account. Collection `bank_requests` on the account server;
  superusers only can read it ([ACCOUNTS.md](ACCOUNTS.md) → Bank requests from Aresium).
- No personal data in the record: the app refuses to send a name that looks like an IBAN or account number, an email
  address, a date, an amount or 5+ digits, and the server refuses the same again (`pb_hooks/lib/personal-data.js`,
  the check of a bank format's name). A person's name typed instead of the bank's cannot be detected.
- A hook mails each request through Resend to `REDACTED-EMAIL` (IONOS), without a Reply-To.
- IP address: in the account server's request log for 5 days (as every request), and in PocketBase's in-memory rate
  limiter (5 per hour per address); not stored with the request.
- Kept until handled (the bank added to Aresium, or decided against), at most 12 months; deleted by hand (the record
  in the admin UI and the email). The nightly backup keeps copies as for all account data (Backups below).
- Basis: Art. 6(1)(f) for the IP address in the logs and the rate limit (security); the request itself is no personal
  data. The public policy names it in its Aresium section before Aresium opens (To do 6).

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

2026-10-26 (ring-access): section 5 of both policies: the saved hub ring ("the applications selected in the hub" /
"die im Hub ausgewählten Anwendungen") is gone from the list of account data, since it is no longer stored. The
controller's notice about sign-ups and access requests stays an email (no push notification), so that passage is
unchanged.

2026-10-27 (Aresium): section 6 → "Aresium" added to both policies (Patrik approved the text with his notes); section
5's first sentence names Aresium as usable without an account; section 7's Resend line names bank formats and bank
names; section 11 names Aresium's contact form. Published by merging to main; the account server's bank_formats and
bank_requests inboxes and the "[Aresium]" contact email were deployed the same day.

2026-10-28 (Aresium receipts): section 6 → "Aresium", one paragraph on receipts in both policies (camera or photo
library, read on the iPhone, photo discarded, what is stored, nothing transmitted); Patrik approved the text.

2026-11-01 (the hub's contact pages): section 4 of both policies names the contact forms on www.ares-empire.de
(among them /contact, /kontakt) and aresium.de, the chosen topic and the install link for a request for an app;
section 3 names the look remembered in the browser by the switch on aresium.de and on the hub's contact pages
(localStorage, § 25(2) no. 2 TDDDG). Patrik approved both texts; published with the pages.

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
4. ~~**Links.**~~ Done 2026-10-25: the login pages, the apps' Settings, and the signed-in hub, aresium.de and
   arestoteles.de (a quiet "Privacy · Imprint" line, desktop and phone) link the privacy policy and imprint.
5. ~~**Backups.**~~ Done 2026-10-25: the one-off copies are deleted, the nightly backup runs ([BACKUP.md](BACKUP.md)),
   and the policy's section 9 (Speicherdauer / Storage period) names it and its periods (Patrik approved the text
   2026-10-25).
6. ~~**Aresium for other people, before it opens**~~: done 2026-10-27. The public policy's section 6 → "Aresium"
   (German and English, approved by Patrik with his notes: no PayPal, no "no AI", no account talk): the bank data,
   categories and sorting stay on the iPhone and never reach our servers; deleting, export and device backups, the
   lock, sending a bank's format or a missing bank's name ("Bank formats" and "Bank requests" sections above), and
   contact through the contact form's route. Section 5 says Aresium works without an account. The netcup AVV needs no
   change. **Rule that keeps the text true:** the `aresium` service stays with Patrik's own accounts (the hub catalog
   has Aresium as "coming-soon", so nobody can ask for it). If anyone else ever gets it, the app asks `GET /api/mode`
   for them, and the policy must name that request again before. The legal check of the server route (AVV entries,
   Groq, transfers, Art. 9, Art. 30, DPIA) is kept on branch `codex/03-aresium-privacy` in case server sorting comes
   back.
7. ~~**Aresium's own contact form (aresium.de/contact, /kontakt), before it goes live**~~: done 2026-10-31 (section 4
   names it, the topic and the install link; section 11 says "contact forms").
8. ~~**The hub's contact pages (Ares Empire, Arestemis; 2026-11-01), with or before them going live:**~~ done 2026-11-01
   (Patrik approved section 4 and the optional section 3 sentence; published with the pages). Before: section 4 of both
   policies says the topic is processed "on aresium.de" only; the hub's pages send it too, and the app. Drafted on
   ares-empire branch `contact-pages-privacy` (section 4: the contact forms on www.ares-empire.de and aresium.de, the
   chosen topic, a request for an app), **needs Patrik's OK**. Optional, his call: a sentence in section 3 on the look
   remembered in the browser by the switch on aresium.de and the hub's contact pages. Set "Last updated" / "Stand" to
   the day it is published. No new recipient, no change to the netcup AVV (the same collection, server and mailbox).
