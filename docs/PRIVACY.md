# Privacy — what personal data the Empire handles

**Written 2026-10-24** (brief E6) from the code of every repo, for the privacy policy
(`www.ares-empire.de/datenschutz`, `/privacy`), the imprint (`/impressum`, `/imprint`) and Apple's privacy answers
(`empire-ios/docs/APP-STORE.md`). Keep it current: a service that starts storing or sending something new updates its
row here, then the pages (`web/legal/`), then the app's `PrivacyInfo.xcprivacy`.

**[lead to confirm]** marks what the code cannot show (server settings, provider contracts). The pages are not served
while they still contain `[lead to confirm]` or `[ADDRESS]` (`webauth/legal.py`).

## Facts that hold everywhere

- **Controller:** Patrik Breeck, `[ADDRESS]` (Patrik decides which address), `REDACTED-EMAIL`. A private
  project, no company; no data protection officer needed (§ 38 BDSG: fewer than 20 people process data).
- **Supervisory authority:** Bayerisches Landesamt für Datenschutzaufsicht (BayLDA), Promenade 18, 91522 Ansbach,
  www.lda.bayern.de (checked 2026-10-24).
- **Host:** one netcup VPS in Germany runs every service below (lead, 2026-10-24); Caddy in front, TLS everywhere.
  Processing agreement (AVV) with netcup signed in the customer panel: **[lead to confirm]**.
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
| **Data** | Email, password (PocketBase stores only a hash), `name` (empty unless set through the API; sign-up does not ask for it), `verified`, `approved`, `services`, `admin`, `ring` (the provinces in the hub's ring), created/updated. |
| **Where** | `/var/lib/empire-accounts/pb_data` (SQLite). |
| **How long** | Until the account is deleted. Unapproved sign-ups stay until Patrik approves or deletes them (no automatic clean-up). |
| **Emails** (Resend) | Confirmation link, password reset, "login from a new location" alert (PocketBase built-in), "approved" mail to the person; to the superusers an approval request naming the new account's email (`pb_hooks/accounts.pb.js`). |
| **Logs** | PocketBase's request log, with the visitor's IP (Caddy's `X-Forwarded-For`, `trustedProxy` in the first migration). Retention and IP logging as set in Settings → Logs: PocketBase defaults are 5 days with IP **[lead to confirm]**. |
| **New-location alerts** | PocketBase keeps a fingerprint per account and device it logged in from (`_authOrigins`) until the account is deleted **[lead to confirm how the fingerprint is made]**. |
| **Admins** | See pending accounts' email, name and creation time to approve them (`admin-visibility.pb.js`, hub `GET /api/empire/approvals`). |
| **Basis** | Account and login: Art. 6(1)(b) GDPR. Logs, rate limits, alerts: Art. 6(1)(f) (security). |
| **Deleting** | The API lets a non-admin delete their own account (`deleteRule`), but no website page or app offers it yet: open (below). |

### Hub (`www.ares-empire.de`, `webauth/server.py`)

- Login, sign-up and reset forms pass email and password to PocketBase on localhost with the visitor's IP (for
  PocketBase's rate limit). The hub stores nothing itself.
- Its log lines (journald) hold the request line and Caddy's address, **not** the visitor's IP (`address_string()`
  is the proxy).
- `GET /api/empire` (website and Empire app): asks Aresium's `/api/pulse` and Aresus's overview with the visitor's
  token for the live lines, cached 60 s per account in memory.
- **Third parties in the browser:** `web/index.html`, `web/login.html` and `wallpaper.html` load fonts from Google
  Fonts (`fonts.googleapis.com`, `fonts.gstatic.com`); `index.html` loads React, Babel and Lucide from `unpkg.com`.
  Every visitor's browser sends its IP to those hosts. aresium.de and arestoteles.de do the same. German courts have
  ruled against Google Fonts loaded this way (LG München I, 3 O 17493/20). **Fix before other people use the
  websites:** self-host the fonts (Space Grotesk is in `web/fonts/` now; JetBrains Mono and Cinzel would follow) and
  the scripts, then delete the "Websites" section of the policy. The legal pages load nothing from other hosts.

### Push service (`empire-push.service`, `push/`)

| | |
|---|---|
| **Data** | Per device: app (bundle id), APNs device token, account id, `sandbox`/`production`, language, created/updated (`push/store.py`). Outbox: the last 200 notifications (time, app, account id or "all", title, body, link, language, result), never a device token. |
| **Where** | `/var/lib/empire-push/push.db`. |
| **How long** | Device: until logout, losing the app's service, Apple calling the token stale, or 60 days without re-registration (daily clean-up). Outbox: last 200 rows. |
| **Recipient** | Apple Push Notification service (title, body, link of each notification, the device token) once the APNs key exists; until then a dry run that sends nothing. Apple's safeguard for US transfers **[lead to confirm]**. |
| **Logs** | Device tokens only as their first 6 characters; no visitor IP (proxy address). |
| **Basis** | Art. 6(1)(b); the iOS permission decides whether the phone shows them. |

### Arestemis (`arestemis.service`, `~/Arestemis`)

| | |
|---|---|
| **Data** | Per account: the hunt (search: kinds, people, places, areas, sizes, rents, move-in dates, sublets, portals, the free "extras" text), active/paused and times; settings (`application_mode`, `own_text` ≤ 5000 chars, `about_me` ≤ 2000 chars, notification switches); matches (listing, state new/saved/applied/dismissed, the AI's reason and warnings, the contact name from the listing, the application text and how it was made); filtered-out listings with reasons. Listings themselves are public portal data (title, rent, size, address or district, description, photo link) and can name a landlord or flatmate. |
| **"About you"** | Free text the AI uses ("22, Informatics at TUM, non-smoker"). The app's caption suggests gender and age (STATUS.md 05:27, because listings restrict on them). Nothing in it is required. |
| **Where** | `data/arestemis.db` in `/root/Arestemis`. |
| **How long** | Hunt, matches, rejected and seen rows: deleted with the hunt (`DELETE /hunts/{id}`, cascade). Rejected: 7 days. Listings no match needs: 30 days. Seen listing ids: 180 days. Settings: no delete route; they stay until the database row is removed by hand. Nothing is deleted when the Empire account is deleted: open (below). |
| **Groq** (Groq, Inc., USA) | Each listing that passes the exact checks: the search, `about_me`, the listing (`llm/provider.py` `verify_messages`). AI applications: the listing, `own_text`, `about_me`, the contact name. "Describe it": the sentence typed (not stored by Arestemis). Groq's DPA includes the EU SCCs; Groq is not in the Data Privacy Framework (web check 2026-10-24) **[lead to confirm: DPA accepted, retention / zero data retention in the Groq console]**. |
| **Telegram** | Only for the account in `TELEGRAM_FALLBACK_USER` (Patrik): a copy of each new match to his own chat, until push works. No other account's data. |
| **Portals** | The server reads WG-Gesucht, Kleinanzeigen, Immowelt (no user data sent). On the phone, listing photos load straight from the portal's image server (`AsyncImage(image_url)`), so the portal sees the phone's IP; "Open listing" opens the portal page. |
| **Logs** | uvicorn's access log (journald) with the visitor's IP (uvicorn trusts `X-Forwarded-For` from 127.0.0.1 by default) and the full path incl. query, e.g. `GET /places?q=garch` **[lead to confirm journald retention]**. |
| **Basis** | Art. 6(1)(b) (the AI check and applications are the service asked for). |

### Aresus (`aresus.service`, `~/aresus`) and Aresync

| | |
|---|---|
| **Data** | About Patrik's server and machines, not about app users: check results, incidents (30 days after resolved), uptime per day (14 days), server vitals, last deploy per repo (commit hash, subject, date), Aresync run reports per machine (machine name, OS, times, counts, log lines with repo names and commits, problems, alerts; 30 days). Machine tokens only as SHA-256. |
| **Users** | Accounts with the `aresus` service (Patrik decides). Their account and push data are covered above. |
| **Telegram** | Aresync's own alerts go to Patrik's chat until push works (`TG_*` in each Aresync config). |
| **Logs** | uvicorn access log with IP, as Arestemis. |

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
  private repo) **[lead to confirm GitHub's DPF listing]**.
- Search (`GET /search?q=`) runs on our server (local model, brief E3); the query is not stored, except in uvicorn's
  access log with the IP.
- On the phone: the vault copy and unsent quick notes in Application Support (file protection), the notes in
  Spotlight (on the device); all deleted at logout.
- Discuss: copies a prompt to the clipboard and opens `claude.ai/code`, only when tapped; Anthropic then gets what
  the user pastes, under their own Claude account.
- The website arestoteles.de keeps its own single password (Patrik only) and loads Google Fonts and unpkg like the hub.

### Contact & support (brief E5, being built)

- Collection `feedback` on the account server: account (deleted with the account), app, kind, message (≤ 5000),
  app version, system ("iOS 27.0 · iPhone"), language, created. Superusers only can read it.
- A hook mails each message through Resend to `REDACTED-EMAIL`, Reply-To the account's email.
- **[lead to confirm]**: which provider hosts the `REDACTED-DOMAIN` mailbox (a recipient), and how long messages are
  kept (suggested: deleted 12 months after the matter is closed).
- Basis: Art. 6(1)(b) for questions about the service, otherwise 6(1)(f).

### Resend (email)

Resend, Inc., USA: sends every email above from `noreply@ares-empire.de` (`smtp.resend.com:2465`). Resend is in the
EU–US Data Privacy Framework and its DPA has the SCCs; stored data (sent-mail logs) is in the US whatever sending
region the domain uses (Resend's GDPR page, 2026-10-24) **[lead to confirm: domain region, log retention on our plan]**.

### Backups and copies

- No off-server backup yet (ACCOUNTS.md, ARESUS-APP.md). netcup snapshots **[lead to confirm]**.
- One-off copies on the server hold personal data: `pb_data.before-services-20261024`,
  `/root/arestemis-backup-before-languages-20261024.db`, `state.json.bak-*` (STATUS.md). Delete them once no longer
  needed, and name the backup's retention in the policy when backups exist.

## Open before other people use the apps

1. **Delete your account** in every app (Apple guideline 5.1.1(v)) and on the website, and make it reach every
   service: PocketBase account (+ its `feedback` rows by cascade), push devices, Arestemis's hunt, settings and
   matches. Today a deleted account leaves its Arestemis rows and its push devices (until 60 days) behind.
2. **Self-host the website fonts and scripts** (hub, aresium.de, arestoteles.de), then drop the policy's
   "Websites" section.
3. **Logs:** set a journald retention (e.g. `MaxRetentionSec=14day` in `/etc/systemd/journald.conf`) and check
   PocketBase's log settings, then put the real numbers into the policy. Consider dropping query strings from
   uvicorn's access log (`--no-access-log` or a filter), since `?q=` carries what people search.
4. **Providers:** confirm the AVV with netcup, the DPAs of Groq and Resend (accepted in their dashboards), Groq's
   retention setting, and the mailbox provider of `REDACTED-DOMAIN`.
5. **Imprint:** the address (`[ADDRESS]`, must be one where post can be served, not a P.O. box) and a second quick
   way to reach Patrik besides email (§ 5(1) no. 2 DDG: a phone number or a contact form).
6. **Links:** the login page links to `/privacy` and `/imprint` now; the signed-in hub, aresium.de and arestoteles.de
   should get the same footer, and the apps get them in Settings (brief E4b).
