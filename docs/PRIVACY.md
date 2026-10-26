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

- **Controller:** Patrik Breeck, REDACTED-ADDRESS, 85748 Garching, `REDACTED-EMAIL`. A private project, no company; a data
  protection officer was considered unnecessary in the original inventory. **Recheck before Aresium opens:** fewer
  than 20 people is not enough to settle this if a DPIA is required (§ 38(1), second sentence, BDSG; see L6 below,
  checked 2026-10-26). Patrik chose the address (2026-10-25); the
  public pages show it only in the policy's controller line and the imprint.
- **Supervisory authority:** Bayerisches Landesamt für Datenschutzaufsicht (BayLDA), Promenade 18, 91522 Ansbach,
  www.lda.bayern.de (checked 2026-10-24).
- **Host:** one netcup VPS in Germany runs every service below (lead, 2026-10-24); Caddy in front, TLS everywhere.
  Processing agreement (AVV) with netcup concluded in the customer panel (Patrik, 2026-10-25). Declared there: affected persons: Interessenten (contact and support messages), visitors of the
  websites, users of the websites and apps (registered accounts); data: Personenstammdaten (name, optional; email),
  Kommunikationsdaten (email, messages), access and usage data (login data, IP addresses, server logs, push device
  ids), content data of the applications (settings, search profiles, notes); no special categories (Art. 9). **The
  declaration at conclusion excluded bank, payment and financial data**, based on the 2026-10-25 phone-only plan.
  The optional auto-sort route agreed on 2026-10-26 changes that: payment data and potentially special-category
  information pass through the server. The signed declaration is historical, not an accurate description of that
  planned route. Update it before opening (exact proposed entries below). No device location.
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

**Today:** owner mode only. **For opening:** phone mode below is agreed in
[ARESIUM-FOR-OTHERS.md](ARESIUM-FOR-OTHERS.md), parts 2, 5 layer 3, 7 and Decisions (2026-10-26); it is not a
claim that the route, consent or deletion behaviour has already been built or verified.

| | Processing for other people (planned) |
|---|---|
| **People and purpose** | Approved Ares account holders using the `aresium` service; managing their finances and, only if enabled, assigning categories to otherwise unsorted payments. Counterparties and people named in booking texts may also be affected. |
| **Phone** | Import files, payments, categories, corrections and sorting rules stay on the person's iPhone; parsing, dashboard and local sorting run there. The controller cannot inspect that stored copy. No import files, raw bank rows or balances are uploaded by the auto-sort protocol; it has no separate bank-identifier fields. Free booking texts can themselves contain identifiers: a random reference is not anonymisation. |
| **Optional auto-sort** | One switch, off by default. For payments local rules cannot sort: date, amount, booking text, counterparty and a random reference per payment, plus category names, go to a new Aresium server route at netcup in Germany. The server sends these fields to GroqCloud and returns a category from that list (or none) per payment. The result is saved on the phone and can be corrected. No payments, credit decisions or access decisions are executed by the AI. |
| **Provider/model** | Groq; planned model family `llama-3.3-70b`. Current documentation lists the production API identifier `llama-3.3-70b-versatile` (G7). Verify the actual identifier and account entitlement before building; no model/provider change is proposed. The plan's “Groq, Inc., USA” conflicts with the current EEA contracting entity, Groq UK Limited (G3); confirm the existing account's agreement before publishing the recipient line. US processing remains relevant (G2). |
| **Storage** | Request/response content exists on the server only while answering the request: no database row, request/response content logs, persistent queue, prompt cache or backup copy. Groq ZDR must be enabled for these requests. This describes payment content, not account records, consent evidence, technical request logs or Groq usage metadata; G1 and the legal check below distinguish them. Actual logging and retention need implementation checks. |
| **Authentication and rate limit** | Account/token used by our server for authorisation and a per-account rate limit; never forward the token, account id, email or end-user IP to Groq. Exact rate-limit state and expiry remain an implementation decision to record here. Existing account and technical security-log retention remains as above. |
| **Basis** | Account: Art. 6(1)(b); optional remote sorting: Art. 6(1)(a), with explicit Art. 9(2)(a) consent for information revealing the consenting person's special categories. Local/manual sorting remains usable without consent. Switch off to withdraw for future sends, including queued retries. Consent wording/version and evidence mechanism must satisfy L2; third-party data requires a separate resolution below. |
| **Phone retention/deletion** | Logout retains and locks the local data to that account. Export, delete-local-data, Leave Aresium and Delete Ares account must follow the plan's export/deletion behaviour. Device backups (iCloud/computer) may contain local data; restoring a backup can restore it. Exports and backups require the person's own deletion. Remote deletion cannot immediately wipe an offline phone; verify how the app processes deletion when it reconnects. |
| **Other AI/import paths** | The plan also proposes AI mapping of unknown CSV header names. No payment values or file preamble may be included. A header can contain personal information; verify the exact path/payload, recipient, legal basis and retention before claiming this is non-personal. Receipts are version 2 and outside this opening. |
| **Public notice** | Prepared in `web/legal/drafts/aresium.de.html` / `aresium.en.html`; exact policy-wide changes and serving caveat in their README. Insert only at opening, after the checklist. No live Aresium policy section exists today. |

**Owner mode, unchanged by this brief:** the owner's bank/PayPal transactions, raw export rows, categories,
rules and corrections stay in Postgres (`aresium-db-1`); imports are parsed and not kept as files. Existing
`EMPIRE_ALLOWED_USERS` limits this mode to the owner list. Manual `npm run ai` / `npm run places` scripts send
transaction fields to Groq for categories and merchant/city to OpenStreetMap Nominatim; Telegram bot/reminders
use only the owner's configured chat. These are internal inventory facts, not part of the new public section.

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

## Opening Aresium: legal check (2026-10-26)

This check prepares decisions and panel entries; it does not record provider acceptance, a completed DPIA or
production verification. Only public sources were read. All external sources below were checked **2026-10-26**;
source IDs resolve to the URLs in the source table. Statements applying law to Aresium are assessments, with
unresolved points identified explicitly. No provider panel, server or other repository was changed.

### 1. netcup AVV: yes, update the declared scope before opening

The existing declaration says no bank/payment/financial data and no Article 9 data. Auto-sort receives and
transmits payment content on netcup infrastructure. Transient handling is processing too (Article 4(2), L1);
the absence of a database does not preserve the old exclusion. Article 28(3) requires the contract to describe
the data types and affected people (L8). **Assessment: update the AVV's processing description/annex**, keeping
the existing account, visitor and contact coverage. This does not mean all of netcup's standard clauses need
rewriting or that an entirely different hosting contract is needed.

N1 confirms the public panel route is **CCP → Stammdaten → Auftragsverarbeitung → AV-Vertrag erstellen**
(also called “AV-Vertrag generieren”), with data and affected-person information. The repo's “AV-Vertrag” is
shorthand for that tab. N1 does **not** publish the current dropdown/checkbox vocabulary or an amendment flow
for an already signed contract. The following are exact proposed German entries, **not claimed to be netcup's
unseen form labels**. Add them to the corresponding data/affected-person descriptions, retaining existing entries;
if only fixed choices are available, choose the matching offered categories and put the detail in a free-text
field/annex. If the existing contract cannot be amended there, have netcup confirm the supported replacement
process. Save the resulting signed contract outside the repo; panel acceptance remains Patrik's action. [N1]

| Add to the declaration | Exact German entry |
|---|---|
| Affected people | **Registrierte Nutzerinnen und Nutzer der Websites und Apps, insbesondere Aresium; natürliche Personen als Zahlungspartner sowie sonstige in Buchungstexten genannte Personen.** |
| Financial/payment data | **Finanz- und Zahlungsdaten: Datum, Betrag, Buchungstext und Zahlungspartner der nicht lokal zugeordneten Zahlungen; zufällige Referenz je Zahlung.** |
| Application content | **Inhaltsdaten der Anwendung Aresium: Kategorienamen und Ergebnisse der automatischen Kategoriezuordnung.** |
| Special categories | **Besondere Kategorien personenbezogener Daten nach Art. 9 Abs. 1 DSGVO, soweit Buchungstexte, Zahlungspartner oder Kategorienamen Angaben zur Gesundheit, zu religiösen oder weltanschaulichen Überzeugungen, politischen Meinungen, Gewerkschaftszugehörigkeit oder sonstige besondere Kategorien offenbaren.** |
| Nature/purpose/storage note, wherever the form allows it | **Optionale automatische Zuordnung von Zahlungen zu Kategorien: verschlüsselte Übermittlung vom iPhone, flüchtige Verarbeitung auf dem Server und Weiterleitung an den vom Verantwortlichen beauftragten KI-Dienst Groq; Rückgabe der Kategoriezuordnung. Keine dauerhafte Speicherung der Zahlungsinhalte, Kategorienamen oder Antworten in Datenbanken, Protokollen oder Sicherungen. Bestehende Konto- und technische Sicherheitsdaten bleiben gesondert erfasst.** |

Remove any blanket **“keine Bank-, Zahlungs- oder Finanzdaten”** and **“keine besonderen Kategorien”** declaration
for the service. Do not claim bank identifiers can never occur inside booking text. The protocol adds no separate
bank/account/card-number fields. The entry for special categories reflects the possible content, not a claim
that every transaction is Article 9 data. Covering a category contractually does not supply the lawful basis for
it; third-party data is still an opening issue below. Groq is commissioned by the controller as a separate
processor; it is not thereby a subprocessor appointed by netcup (roles assessed under L8).

### 2. Groq: DPA, retention, location and international transfer

| Question | Finding and action |
|---|---|
| **Does a DPA exist; must it be signed separately?** | Yes. The Customer DPA is incorporated in the Services Agreement. Schedule A treats electronic acceptance as signature; §8 incorporates SCCs (Module 2 for controller → processor). Schedule A contemplates special-category content, without supplying its lawful basis. The Services Agreement accepts click/order/use. Preserve evidence of the agreement actually applying to this account; a separate DPA button is not established. [G2], [G3] |
| **Which Groq entity?** | The plan says Groq, Inc., USA. Current EEA terms specify Groq UK Limited; most other customers contract with Groq LLC. **Open:** the existing account's applicable contract. Use the matching recipient insertion in the draft README; do not publish “Inc.” solely from the older plan. [G3] |
| **Normal retention** | Ordinary inference is not retained by default, but reliability/abuse logs may contain input/output for up to 30 days, longer if legally required. Batch files normally last 30 days; fine-tuning data until deletion. [G1] |
| **With ZDR** | All customers can enable ZDR globally or per feature in Data Controls. It excludes reliability/abuse content retention and disables persistence-dependent features. Usage metadata is still retained and excludes inputs/outputs. Its precise fields and retention period are **not confirmed**. Use synchronous inference only; verify the setting for the actual organisation, feature and API key. [G1] |
| **Training / model publisher** | The Agreement prohibits training/fine-tuning on inputs/outputs without explicit customer permission/instruction. Give none. Groq's FAQ says customer content is not shared with model developers/publishers. Hosting a Llama model is not evidence that Meta receives requests. [G3] (§4.2), [G6] |
| **Where?** | Retained customer content is in US GCP buckets. This does not establish the live inference location. The DPA permits US and other countries; Groq's platform advertises infrastructure in several regions. **Open:** account-specific inference routing, support access, metadata locations and onward transfers. No EU-only or US-only inference guarantee was found. Confirm them before publication. [G1], [G2] (§8.1), [G4] |
| **Subprocessors** | The DPA points to `trust.groq.com/subprocessors`; its full list did not render in the public web/curl check. The public Trust Center shows Stytch (identity), Google Cloud Platform (cloud), Stripe (billing) and CloudFlare (WAF/CDN). These are not proof that every one receives payment content or that the list is complete. Obtain the current complete list, roles and countries; subscribe to changes. DPA §7 provides general authorisation and a 15-day notice/objection process. [G2], [G6] |
| **DPF certified?** | No active Groq certification was found in the official list. Its public search backing endpoint returned `RecordCount: 0` for `Groq`, `Groq, Inc.` and `Groq LLC` with `Status: Active`; `Groq` also returned zero inactive matches. A positive control (`Microsoft`) returned one active match. The JavaScript list shell alone was not treated as evidence of absence. This is a dated search result, not a guarantee about future certification. [G5] |
| **Transfer basis** | **Use SCCs, not a claimed Groq DPF adequacy basis, for the US processing.** For a direct controller → processor transfer, G2 specifies Module 2. The Commission lists a current UK adequacy decision, renewed in December 2025: Article 45 can cover the EU → UK leg if the recipient is Groq UK Limited. It does not itself cover onward US processing. Confirm the entities and the mechanism for each leg; the DPA applies SCCs to the extent legally required. [G2], [L7], [L11] |

**Transfer assessment still needed:** SCC clause 14 requires a documented assessment of destination laws/practices
and safeguards. Prepare it for the actual chain; obtain Groq's relevant assurances, complete the processing
description with payment data/possible special categories, and keep it with the DPA. ZDR, minimisation and TLS
reduce exposure, but inference still requires readable data at the provider. TLS does not remove that access or
make an unsupported transfer lawful. If adequate safeguards cannot be demonstrated, do not send the content.
Switching on auto-sort is Article 6/9 consent, not a substitute Article 49 international-transfer derogation. [L7]

### 3. Consent, special categories and other people's data

**Assessment: obtain explicit Article 9(2)(a) consent as well as Article 6(1)(a) consent for remote auto-sort.**
Money amounts alone are not automatically special categories. However, free booking text, counterparties and
user-created category names can reveal treatment, religious affiliation, political donations or union membership.
The route receives these fields without a reliable exclusion, and the random reference does not anonymise them.
The EDPB requires both an Article 6 basis and an Article 9 exception for sensitive data; the CJEU confirms that
transaction information allowing health inferences can fall within Article 9 (its pharmacy-order case is an
analogy, not a ruling about this app). No other Article 9 exception has been established here. [L2], [L3], [L4]

The agreed **single switch can remain the affirmative consent action**, but a bare “Auto-sort” label and a policy
link do not demonstrate explicit, informed consent. Show the specific processing, recipients/US transfer and
sensitive-data scope alongside it; see the bilingual wording in the draft README. EDPB consent guidance permits
explicit electronic statements; it does not require a paper signature. Keep the same local/manual functionality
when off. Withdrawal is the same switch and stops new requests/retries; it cannot undo a request already sent.
Store proof of the affirmative action, wording/version, time and withdrawal without a payment history. The exact
evidence mechanism, minimal identifiers and retention remain **open implementation decisions**; choose and document
them before opening rather than silently introducing permanent consent telemetry. [L2]

**Unresolved lawful basis for counterparties:** a user cannot consent on behalf of every private person named in
a payment. Do not present the user's consent as covering those people. Ordinary third-party data needs its own
Article 6 analysis (including a documented balancing test if relying on legitimate interests); Article 14 requires
notice or a properly established exception for indirectly obtained data. Special-category information about a
third party needs its own Article 9 condition. No applicable exception or third-party consent has been confirmed.
Before enabling remote sorting, resolve this with a qualified assessment and/or reliable removal of such data
on the phone; filtering after upload would be too late. Do not silently change the agreed protocol or claim an
unbuilt filter in the public text. The user-facing drafts must be adjusted if the resolution changes the payload.
[L1], [L3]

### 4. Record of processing, DPIA and data protection officer

**Record of processing (Article 30): prepare/maintain it.** A private, free project has no automatic exemption.
The household exclusion concerns purely personal/household activity; Recital 18 also addresses providers of the
means for others' household processing. **Assessment:** do not rely on that exclusion for this account-based
hosted service for other people. Under Article 30(5)'s small-organisation exemption, recurring processing and
special-category processing are each reasons not to rely on it, irrespective of having fewer than 250 employees.
This feature is recurring by design; its use by a few friends is not merely occasional. [L1], [L5]

This inventory is the foundation, not a claim that a complete signed-off record exists. The opening record must
identify the controller/contact (refer to Facts rather than adding personal details to new files), purposes,
affected people including counterparties, data categories, recipients, countries/safeguards, deletion periods and
security measures. Complete the currently unknown rate-limit, consent-evidence and provider-metadata details.
Keep the current version available to the authority on request. [L5]

**DPIA (Article 35): treat it as an opening requirement for auto-sort pending a documented contrary assessment.**
The small friend group does not meet an obvious large-scale Article 35(3)(b) trigger. But the DSK mandatory list,
published by BayLDA, item **11** covers AI processing for assessing personal aspects; that item contains no
large-scale threshold. **Assessment:** categorising personal transactions can assess economic behaviour and is
likely within it. AI alone is not a universal DPIA trigger (BayLDA expressly says so). Whether this limited
classification is an assessment within item 11 remains a legal classification to confirm; no exemption is
established here. An unqualified “no DPIA because only friends / no storage” would be unsupported. [L1], [L9], [L10]

Prepare a proportionate DPIA before enabling the route: processing/purpose, necessity and proportionality, risks
and safeguards, with attention to sensitive data, counterparties, provider access, mistaken categories, prompt
injection in booking texts, logging failures and US/onward transfers. Include evidence from the actual route,
consent and ZDR checks; this legal check is **not itself a completed DPIA**. If unmitigated high residual risk
remains, Article 36 requires prior authority consultation. [L1], [L10]

**DPO consequence:** the old “fewer than 20 people, so no DPO” statement was incomplete. Section 38(1), second
sentence, BDSG requires designation independently of headcount where processing is subject to a DPIA. Resolve
the DPIA classification and the resulting designation/contact-publication obligations before opening. An optional
DPIA undertaken solely as a precaution does not itself establish that statutory trigger. No DPO has been appointed
by this brief, and the owner should not simply assume he can independently oversee his own controller decisions.
[L6]; [L1] (Articles 37–38)

### 5. App Store privacy label

Apple's definition is: transmitting data off device so it can be accessed **“for a period longer than what is
necessary to service the transmitted request in real time.”** This is the relevant excerpt; the full definition
and Apple's examples are at A1. Apple also exempts processing solely on device and specifically
describes immediately discarded request data. This is Apple's disclosure definition, not the GDPR's definition
of processing. [A1]

**For verified phone mode plus synchronous, content-free auto-sort:** do not add **Other Financial Info**, Health
or Sensitive Info just for payments handled only during that request. ZDR must cover Groq too; a retained prompt,
error log, cache, batch or support copy would invalidate that conclusion. Optional consent alone would not exempt
retained financial data. The label remains **data collected: Yes**, **linked to identity: Yes**, **App Functionality**,
**no tracking**, for **Email Address, Name (optional account field), User ID and Customer Support** already present
in the account/support flow. It is not “email only.” Check any retained technical identifiers/usage data too. [A1]

The read-only `empire-ios/docs/APP-STORE.md` currently lists **Other Financial Info** in both Aresium's manifest
table and App Store answers because it describes owner server mode. The proposed reduction is conditional:
if the **distributed build still supports owner server mode that retains financial data**, disclose **Other
Financial Info** for that build as well; labels must cover differing users/modes. Do not remove it merely because
friends get phone mode. Coordinate the final build's manifest and App Store Connect answers with the iOS lead;
no file in that repo was changed here. [A1]

### 6. Further opening checks the plan needs

- **No logging means the whole path:** review reverse proxy, route middleware, SDK errors/retries, tracing, crash
  reports, queues, temporary files, caches, swap/core dumps and backups. Test success, invalid body, provider error,
  timeout and rate-limit paths with made-up sentinel content; search every relevant sink for it. Do not send real
  bank exports as test evidence. Retain only a summary of checks. Record the technical metadata that does remain
  and its exact expiry. These checks implement the minimisation/security duties; they are not yet performed. [L1]
- **Consent enforcement:** protect the new route with service access checks and rate limiting, separate owner
  data access, validate allowed fields and category-only output, and prevent future sends/retries after withdrawal.
  No token/account/email/end-user-IP forwarding to Groq. Decide how consent is proved without storing payloads.
  A random reference alone does not make financial text anonymous. [L1], [L2]
- **Deletion/backup:** verify local account isolation, logout retention, leave/delete/export, offline deletion and
  restored backups. The current policy promises deletion across services; the draft README narrows that promise
  to what server and phone can actually do. Never claim that deleting the app remotely deletes user-held exports
  or device backups. [L1]; plan part 2
- **Unknown CSV headers:** the plan's assumption that headers are never personal data is unverified. Strip values,
  preambles, account names and identifiers before any AI path; inspect made-up adversarial headers. Document the
  actual route and update notice/consent/label if personal data can leave. Keep payment rows out of support messages.
  Do not promise non-personal input merely because a string is called a header. [L1]
- **Transparency and incidents:** publish the full bilingual changes at opening, including recipients, transfers,
  retention and withdrawal; keep a minimal rights-request and incident response procedure. The revised section 11
  avoids denying all profiling: category analysis may evaluate economic behaviour, while the agreed app makes no
  Article 22 decision with legal or similarly significant effect. [L1] (Articles 4(4), 13–14, 22, 33–34)
- **Draft exposure:** `legal.py` does not map any draft, but authenticated static serving can expose files under
  `web/legal/drafts/` if deployed. Exclude the directory from deployment or resolve the static route separately;
  `DRAFT_MARKERS` do not guard this path. See the draft README. No server code was changed.

### Sources (all checked 2026-10-26)

| ID | Public source and what it supports | Checked |
|---|---|---|
| N1 | [netcup: Auftragsverarbeitung][N1] — panel navigation and declared data/people, not hidden form categories | 2026-10-26 |
| G1 | [Groq: Your Data][G1] — content versus usage metadata, default retention, ZDR controls, US retained-data location | 2026-10-26 |
| G2 | [Groq Customer DPA][G2] — incorporation, processor role, special data in Schedule A, subprocessors, SCCs | 2026-10-26 |
| G3 | [Groq Services Agreement][G3] — acceptance, contracting entity, §4.2 training restriction, scope/exclusions | 2026-10-26 |
| G4 | [Groq Platform][G4] — global infrastructure, not an account-specific routing guarantee | 2026-10-26 |
| G5 | [Official DPF list][G5] — JavaScript UI; [its public search endpoint][G5-api] was queried as described above | 2026-10-26 |
| G6 | [Groq Trust Center][G6] and [FAQ][G6-faq]; [linked subprocessor list][G6-list] did not render completely | 2026-10-26 |
| G7 | [Groq supported models][G7] — current Llama API identifier and production classification | 2026-10-26 |
| L1 | [GDPR, official EUR-Lex text][L1] — Articles 2, 4–9, 13–14, 22, 25, 30, 32–38 and Recital 18. Direct pages returned a robot/JavaScript challenge; relevant official search-index passages were checked, supplemented by EDPB/BayLDA sources below. | 2026-10-26 |
| L2 | [EDPB consent guidelines 05/2020][L2] — explicit electronic consent, demonstration and withdrawal, especially §§93–99 | 2026-10-26 |
| L3 | [EDPB: lawful processing][L3] — Article 6 basis plus Article 9 condition for special categories | 2026-10-26 |
| L4 | [CJEU C-21/23 press release][L4] — health inferences from pharmacy-order data; analogy explained above | 2026-10-26 |
| L5 | [EDPB small-business compliance guide][L5] — Article 30 record contents and occasional-processing exemption; [2025 EDPB/EDPS opinion][L5-opinion] discusses the existing exemption and a proposed simplification, not proof of an enacted amendment | 2026-10-26 |
| L6 | [§38 BDSG, official text][L6] — DPO designation and DPIA trigger independently of headcount | 2026-10-26 |
| L7 | [Commission SCC Decision 2021/914][L7] — Module 2 and clause 14 transfer assessment | 2026-10-26 |
| L8 | [EDPB Article 28 opinion 18/2021][L8] — contract descriptions, data types and affected people | 2026-10-26 |
| L9 | [DSK mandatory DPIA list, BayLDA publication][L9] — item 11 (page 3); [BayLDA DPIA guidance][L9-guide] explains the list is not exhaustive | 2026-10-26 |
| L10 | [BayLDA AI guidance][L10] — not every AI use triggers a DPIA; individual risk assessment | 2026-10-26 |
| L11 | [Commission adequacy decisions][L11] — UK GDPR adequacy, including December 2025 renewal; US coverage limited to participating DPF organisations | 2026-10-26 |
| A1 | [Apple: App privacy details][A1] — definition of collection, real-time/on-device guidance, all-user/mode disclosure | 2026-10-26 |

[N1]: https://www.netcup.com/de/helpcenter/dokumentation/general/avv
[G1]: https://console.groq.com/docs/your-data
[G2]: https://console.groq.com/docs/legal/customer-data-processing-addendum
[G3]: https://console.groq.com/docs/legal/services-agreement
[G4]: https://groq.com/platform
[G5]: https://www.dataprivacyframework.gov/list
[G5-api]: https://dpfapi.azurewebsites.net/api/participants
[G6]: https://trust.groq.com/
[G6-faq]: https://trust.groq.com/faq?s=9pcm46fyh5sypzqgtfto
[G6-list]: https://trust.groq.com/subprocessors
[G7]: https://console.groq.com/docs/models
[L1]: https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng
[L2]: https://www.edpb.europa.eu/sites/default/files/files/file1/edpb_guidelines_202005_consent_en.pdf
[L3]: https://www.edpb.europa.eu/sme/be-compliant/process-personal-data-lawfully_en
[L4]: https://curia.europa.eu/site/upload/docs/application/pdf/2024-10/cp240159en.pdf
[L5]: https://www.edpb.europa.eu/sme/be-compliant/be-compliant_en
[L5-opinion]: https://www.edpb.europa.eu/system/files/2025-07/edpb_edps_jointopinion_202501_proposalsimplification_en.pdf
[L6]: https://www.gesetze-im-internet.de/bdsg_2018/__38.html
[L7]: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex%3A32021D0914
[L8]: https://www.edpb.europa.eu/system/files/2021-05/edpb_opinion_202118_lithuaniansaart28sccs_en.pdf
[L9]: https://www.lda.bayern.de/media/dsfa_muss_liste_dsk_de.pdf
[L9-guide]: https://www.lda.bayern.de/de/thema_dsfa.html
[L10]: https://www.lda.bayern.de/de/ki.html?WAN=521786
[L11]: https://commission.europa.eu/law/law-topic/data-protection/international-dimension-data-protection/adequacy-decisions_en
[A1]: https://developer.apple.com/app-store/app-privacy-details/

## Published

2026-10-25: Patrik approved the text, the AVV with netcup is concluded, journald keeps 14 days
(`deploy/journald/retention.conf`), the address is filled in (his choice), the imprint's second contact route is the
contact form.

2026-10-26 (ring-access): section 5 of both policies: the saved hub ring ("the applications selected in the hub" /
"die im Hub ausgewählten Anwendungen") is gone from the list of account data, since it is no longer stored. The
controller's notice about sign-ups and access requests stays an email (no push notification), so that passage is
unchanged.

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
6. **Aresium opening checklist (2026-10-26):** complete every item below before access is given to others; findings,
   exact panel text and dated sources are in “Opening Aresium: legal check” above. Nothing below is marked complete.

### Aresium opening checklist

1. **Resolve the legal scope:** counterparties' Article 6/9 basis and Article 14 notice/exception; DPIA item 11
   classification, complete DPIA as required, and resulting §38 BDSG DPO obligation. Complete the Article 30 record
   using this inventory and the actual security/retention settings. Preserve decisions outside the repo without
   adding users' personal data here.
2. **netcup panel (Patrik):** add the German affected-person, financial-data, application-content and possible
   special-category entries above; remove the financial/special-data exclusions. Verify the amended/generated
   contract actually covers transient processing; retain it outside the repo. Exact hidden form labels remain open.
3. **Groq agreement (Patrik):** confirm the applicable legal entity and acceptance of Services Agreement/DPA/SCCs;
   preserve evidence, obtain full subprocessors/countries and change notices, confirm the inference/access/metadata
   locations and retention, and complete the transfer assessment. Verify a production model covered by the DPA;
   the Agreement excludes beta services unless otherwise specified (G3 §3.6). Give no training permission.
4. **Groq ZDR (Patrik):** enable it in the actual organisation's Data Controls for the synchronous endpoint/API key
   used by Aresium; disable persistence features and verify no content logging option is enabled. Recheck after
   provider/configuration changes. Public docs establish availability, not the account's current setting. [G1]
5. **Build and verify consent:** explicit bilingual sensitive-data statement by the single off-by-default switch,
   policy link, local/manual use without it, proof/version and documented retention. Withdrawal stops subsequent
   sends and queued retries. Resolve the header-mapping path before it can send personal information.
6. **Server route no-logging check (lead):** synthetic sentinels through success/error/timeout/invalid/rate-limit
   paths; verify proxy/application/SDK logs, caches, queues, temporary files, crash dumps and backups contain no
   request/response content. Confirm account/service authorisation, owner-data isolation and rate limits; do not
   forward authentication or user-identifying headers to Groq. Record actual technical metadata and expiry.
7. **Phone lifecycle check (iOS lead):** account isolation, logout retains data, export/leave/delete works, offline
   device and restored backup behaviour matches the drafted policy. Confirm server content is transient and phone
   category corrections persist locally.
8. **App Store answers (Patrik/iOS lead):** reconcile `empire-ios/docs/APP-STORE.md`, the distributed build's privacy
   manifests and App Store Connect. Phone-only verified transient auto-sort adds no financial collection; retain
   **Other Financial Info** if owner server mode remains in that build. Keep Email Address, Name, User ID and
   Customer Support, identity-linked/App Functionality/no tracking; inspect other retained technical data. [A1]
9. **Insert and approve public texts at opening:** apply `web/legal/drafts/README.md` to both policy languages,
   selecting the confirmed Groq entity/transfer text, including storage, consent withdrawal, local deletion and
   section 11. Check every promise against the built feature. Do not publish the draft directory as static content;
   `legal.py` has no draft route, but authenticated static serving is a separate exposure path. The current live
   policies stay untouched until opening. Only then grant Aresium access/open the hub entry.
