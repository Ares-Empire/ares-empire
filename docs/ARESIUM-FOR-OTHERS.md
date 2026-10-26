# Aresium for other people — plan

**Draft 2026-10-26** (Claude, for Patrik). Nothing here is built yet. Decisions marked **D1–D8** wait for Patrik;
measurements **M1–M5** come before the choices that depend on them. Server: `~/aresium`; app: `empire-ios/Aresium`.

## What it is

Aresium is Patrik's finance dashboard (aresium.de and the iPhone app): bank and PayPal exports go in, every payment
gets a category, and the app shows where the money goes by month and category. "For other people" means anyone Patrik
approves can use the app for their own money, with their data on their own iPhone.

## Already decided (Patrik)

- **Their data stays on their iPhone:** imports, categories, storage. No bank data on any server of ours. Patrik's own
  data stays on the server for aresium.de (2026-10-25; [PRIVACY.md](PRIVACY.md) → Facts, `empire-ios/CLAUDE.md` → Open 5).
- **A plan and tests first** (2026-10-25): imports from other banks; suggested categories people change and extend;
  sorting learned from their own corrections; auto-sort for the rest only if they switch it on (Apple's on-device
  model, or a server that stores nothing); each layer measured on Patrik's own transactions before choosing.
- **Receipts** (2026-10-26, new): take a photo of a receipt in the app; it adds it to the right payment and sorts the
  items into categories. Keeping the photo with the payment: probably too bulky (Patrik's first take, D4).
- Import stays in the app (2026-10-23). The privacy policy gets Aresium's section before anyone else gets it
  ([PRIVACY.md](PRIVACY.md) → the rule).

## Aresium today (what this plan builds on)

From the code on 2026-10-26 (`~/aresium`, `empire-ios/Aresium`):

- **Server:** TypeScript on Node (`src/web/server.ts`), Postgres through Prisma. 1,246 transactions, 246 rules,
  25 corrections (restore test 2026-10-25).
- **Imports:** VR Bank CSV (`src/import/vrbank-csv.ts`), VR Bank CAMT XML (`camt.ts`), PayPal CSV (`paypal-csv.ts`).
  Duplicates are refused by `(source, externalId)` (`core.ts`). The app parses nothing: it reads the file as UTF-8 and
  sends the text to `POST /api/import`.
- **Sorting:** (1) keyword rules on every import (`src/sync/categorize.ts`); (2) an AI pass by hand only (`npm run ai`,
  Groq `llama-3.3-70b`, `src/enrich/llm.ts`); (3) Patrik's own changes (Switch/Add). Each transaction records who set
  its category (`categorySource`: rule, llm, manual); every Switch is logged in `CategoryCorrection`.
- **Categories:** one flat list of 22 (`scripts/seed-categories.ts`), names partly German, partly English ("Drogerie",
  "Groceries"); icons and colours fixed per name in code (`src/data/queries.ts` → `CAT_META`). One category per
  transaction; "tags" show it under more categories without splitting the amount. **No splits.**
- **Numbers:** the server computes the whole dashboard (`src/data/dashboard.ts`, `GET /api/data` version 2); the app
  and the website only display it. The app keeps it in memory; on the phone only the widget's totals are saved.
- **One user:** no owner column anywhere, one import lock, a personal config (`config/personal.json`), an AI prompt
  about Patrik. Access is limited to `EMPIRE_ALLOWED_USERS`.

## The plan, part by part

### 1. One app, two modes

Patrik keeps **server mode** (as today). Everyone else gets **phone mode**: the same screens, with the data and the
calculations on the phone. The Aresium server tells the app which mode an account has (the owner list decides) and
serves no data to anyone else.

The screens already show a ready-made dashboard computed elsewhere. In phone mode the phone must compute that same
dashboard, run the imports and sort. That logic exists today only in the server's TypeScript (about 1,000 lines:
parsers, duplicates, rules, dashboard, recurring payments). **D1** decides how the phone gets it.

### 2. Where the data lives on the phone

- **Storage:** Apple's SwiftData in the app's own folder, protected by the iPhone's data protection. The widgets get
  their numbers from the same small snapshot as today.
- **Backup and a new iPhone:** the iPhone's own backup (iCloud or computer) includes the app's data, so a restored
  phone has it. Without a backup, deleting the app or losing the phone loses the data. The app says so once, plainly,
  and offers **Export** (all data as one file, through the share sheet) and **Import from export**. Syncing between
  one's own devices through the person's own iCloud (CloudKit, not our server) is possible later.
- **Logout keeps the data.** Today every app forgets its data on logout, because the server has the real copy. In
  phone mode the phone has the only copy, so logout locks it to the account (shown again only when the same account
  logs in) and deletes nothing. Deleting happens only on Leave Aresium, Delete Ares account, or "Delete the data on this
  iPhone", each after offering an export. (The central logout, `empire-ios/prompts/09-central-logout.md`, does not
  touch Aresium's data, because phone mode does not exist yet; phone mode must keep it that way.)

### 3. Imports from other banks

- **Standard formats first:** most German banks offer CAMT (XML) and many MT940; one reader each covers many banks.
  The CAMT reader exists (written for VR Bank; to test with other banks' files). Which bank offers what is checked per
  bank, not assumed.
- **Bank CSVs:** one CSV reader with a small profile per bank (column names, separator, date and number format, text
  encoding), recognised by the header line. Many German bank CSVs are not UTF-8 (Windows-1252 / ISO-8859-1); the app
  reads only UTF-8 today, which would break umlauts. An unknown CSV opens a short "which column is what" screen; the
  answer is saved as a profile on the phone.
- **Order:** the banks of the first people (**D5**), then the common ones (Sparkasse, Volksbank, ING, DKB, comdirect,
  N26, Revolut, Trade Republic), PayPal (exists), credit cards later.
- **Test files:** made-up files with each bank's real header and formats; never anyone's real export in a repo.
  Sources for the formats: the banks' export pages, and open-source importers that already describe them (for example
  the Firefly III data importer's bank configurations).
- **Help in the app:** "How to export from <bank>", a few steps per bank. Getting the file out of the bank app is the
  hardest step for most people.
- **Duplicates:** the same as today, plus two fixes found on the way: the same period imported once as CSV and once as
  CAMT creates duplicates today (different ids), and two identical payments on one day in a VR CSV count as one.
- **Several accounts per person** (current account, card, PayPal): the accounts table exists, but the balance line
  assumes one bank account; fix. Money moved between one's own accounts is found by matching (same amount, opposite
  sign, within a few days, own IBAN) and counted as Transfer, like PayPal top-ups today.
- **Not now:** automatic bank access. FinTS straight from the phone is possible (Patrik's roadmap, phase 4) but needs a
  product registration with the German banking association and TAN handling. Account-access providers (PSD2
  aggregators) run on someone else's server and break the rule above, so no.

### 4. Categories

- **A starter set**, each with a name in English and German (shown in the app's language), an icon, a colour and a kind
  (expense, income, transfer). Based on today's 22, cleaned up: one language per name, and some that students need
  (transport and Deutschlandticket, insurance, phone and internet, gifts, cash withdrawals). The list is settled with
  Patrik before building.
- **People change it:** rename, add, delete (its payments move to another category), merge; pick icon and colour.
  Icons and colours are stored per category, not fixed by name in code.
- **Splits** (new): one payment divided into parts with their own category and amount. Receipts need it (part 6);
  shared bills use it too. The server gets the same, so Patrik's receipts work in server mode.
- Flat list, as today (no subcategories).

### 5. Sorting: three layers

Every category shows where it came from (starter rule, learned, auto, you), as today's "via rule / llm / manual".

1. **Starter rules:** a list shipped with the app: common German merchants and patterns (REWE, Aldi, Lidl → Groceries;
   dm, Rossmann → Drugstore; DB, MVV, FlixBus → Transport; Spotify, Netflix → Subscriptions; salary and rent
   patterns). The same for everyone, updated with the app.
2. **Learned from their corrections:** when someone moves a payment to another category, the app remembers it for that
   merchant (the name cleaned of card numbers, cities and dates) and asks once: "Also the 12 other payments to
   REWE?". Future payments from that merchant follow. Own rules ("text contains …") as today. This layer should sort
   most payments, because a few merchants make up most of them (M2 checks this).
3. **Auto-sort, only if switched on**, for what 1 and 2 leave open (**D2**):
   - **Apple's on-device model:** nothing leaves the phone. Needs an iPhone 15 Pro or newer with Apple Intelligence on;
     German is supported (checked on the MacBook's model list, 2026-10-26).
   - **Apple's Private Cloud Compute model** (new in iOS 27): a larger model on Apple's servers; Apple stores no
     prompts; free for apps under 2 million first downloads; needs an entitlement; each user has a daily limit. Data
     leaves the phone, but to Apple, not to us.
   - **Our server** calling an AI provider and storing nothing (like Groq today): data passes through our server and a
     third party, which means a privacy-policy section, a processing agreement and cost. Only if the first two fall
     short.

### 6. Receipts (new)

**What it does:** take a photo of a receipt → the app reads the items and the total → finds the payment (a card
payment usually reaches the account one to three days later) → splits it into categories (REWE €47.83 → Groceries
€38.20, Household €6.99, Drugstore €2.64). Paid in cash: the receipt becomes a cash entry, so cash spending shows up
too.

**Is it possible?** Yes, with Apple's own tools and nothing leaving the phone:

- **Camera:** Apple's document scanner (VisionKit) finds the receipt's edges and straightens it; a long receipt can be
  taken in several pictures. Works on every iPhone.
- **Reading:** Apple's text recognition reads it (Vision; since iOS 26 it also recognises structure such as tables,
  though one developer reports that receipt lines came out as plain lines, so we expect to rebuild the "item | price"
  rows from the positions ourselves). Since iOS 27, Apple's on-device model also reads images directly, and comes with
  ready-made text-recognition and barcode tools.
- **Understanding:** the on-device model turns the text (or the photo) into a fixed structure: shop, date, total,
  items (name, quantity, price), discounts, deposit (Pfand). Apple's "guided generation" makes it answer in exactly
  that structure.
- **Checking:** items plus discounts must add up to the total, and the total must match the payment. Most German
  receipts also carry the cash register's legally required signature data, often as a QR code; as far as I know it
  holds the total per VAT rate, cash or card, and the time, which would give an exact total to check against (to
  confirm on real receipts, M4).
- **Sorting the items:** the same layers as payments, per item and shop ("H-MILCH 1,5%" at REWE → Groceries, learned
  once and kept); the model for new items.

**The hard parts:** shortened item names; faded thermal paper; discount, coupon and deposit lines that belong to
another line; "2 x 1,29" lines. Restaurants need no item lines (one category). Older iPhones without Apple
Intelligence can read receipts but sort items only by what they learned.

**Keeping the photo (D4):** recommended no by default: keep the read lines (a few kilobytes per receipt). A
compressed photo is roughly 0.1–0.3 MB; at 40 receipts a month that is about 50–150 MB a year on the phone (my
estimate), for pictures rarely looked at. Offer "Keep photo" per receipt for things with a warranty (what the
Rechnungen folder does today).

**Later:** digital receipts (REWE eBon, Lidl Plus, dm and others send PDFs): shared into the app, they need no camera
and are read exactly.

**Needs:** splits (part 4); iOS 27 for the image route (the apps require iOS 26 today; the text route works on 26).

### 7. Privacy, App Store, opening

- Aresium's section in the privacy policy, in German and English: data on the phone; what auto-sort sends where (none,
  Apple, or us); the account. App Store privacy label: only the account (email) is collected; no financial data.
- Apple reviews an app before external testers get it: a demo account plus a made-up bank file for the reviewer
  (`empire-ios/docs/APP-STORE.md`).
- Then Aresium goes from "coming soon" to open in the hub catalog; Patrik approves people as for every app.
- When a file cannot be read, Contact & support offers to send only the bank's name and the file's header line, never
  payments.

## Things you may have forgotten

My additions, each with what I would do. Several are in the parts above already.

| # | What | My take |
|---|---|---|
| 1 | **Backup:** the data exists once, on the phone | Now: rely on the iPhone's backup, say so, offer export (part 2). iCloud sync later |
| 2 | **Logout must not delete** the only copy | Now (part 2) |
| 3 | **Several accounts and transfers** between them | Now (part 3) |
| 4 | **Cash:** withdrawals and cash spending | Withdrawals as their own category now; cash spending through receipts (part 6) |
| 5 | **File encodings** other than UTF-8 | Now (part 3) |
| 6 | **"How to export from your bank"** help | Now: first run and import screen |
| 7 | **First run and empty screens** (no data yet; try with sample data) | Now |
| 8 | **Category names in both languages**; today's mix | Now (part 4) |
| 9 | **Face ID lock** for the app | Later, optional; the app-switcher cover (Open 12) comes first |
| 10 | **Budgets, savings goals, shared bills with flatmates** | Later (already on the Aresium roadmap); splits make shared bills easier |
| 11 | **An answer key for measuring:** today's categories are mostly guesses by rules and Groq; only 25 were corrected by hand | Patrik checks categories once per merchant (a few hundred merchants instead of 1,246 lines), **D7** |
| 12 | **Widgets in phone mode** | They read the phone's snapshot as today; small change |
| 13 | **The website:** others have nothing on aresium.de | Say so on the site's login: "Aresium for others is the iPhone app" |
| 14 | **Leaving or deleting** removes the phone's data | After offering an export (part 2) |

## Decisions for Patrik

- **D1 — How the phone gets the logic.** Recommended: **one engine**. Today's TypeScript parsers, rules and dashboard
  become pure functions (no database, no Node-only parts); the server runs them in Node as now, and the app runs the
  same file in JavaScriptCore, Apple's built-in JavaScript engine (allowed in App Store apps when the code ships inside
  the app). A fix or a new bank lands once, and both places give the same numbers. The alternatives: rewrite it in Swift
  for the phone and keep two copies that must stay identical (every change twice), or move Patrik to phone mode as well
  (one Swift engine, but it changes his website imports, the Groq pass and the Telegram bot). First step either way: a
  short test run (M5).
- **D2 — Auto-sort route.** Recommended: measure Apple's on-device model and Apple's Private Cloud Compute (M3); our own
  server only if both fall short.
- **D3 — Is auto-sort off by default?** Already decided: yes, people switch it on. Open: one switch for everything, or
  "ask me for each import"? Recommended: one switch in Aresium's settings, off.
- **D4 — Receipt photos.** Recommended: not kept by default; "Keep photo" per receipt.
- **D5 — Who are the first people, and which banks do they use?** That decides which bank formats come first.
- **D6 — iOS 27 for receipts?** Recommended: receipts need iOS 27 (better reading through the image route); the rest of
  phone mode stays on iOS 26.
- **D7 — Answer key session:** about 30–45 minutes going through merchants and their categories (I prepare the list,
  on the Mac, not committed anywhere).
- **D8 — Apple Intelligence on the MacBook** (System Settings → Apple Intelligence & Siri; downloads the model, a few
  GB) so I can measure the on-device model on the Mac now. It is switched off today
  (`appleIntelligenceNotEnabled`, 2026-10-26). The other way is to measure on the iPhone once TestFlight runs. The
  image input needs macOS/iOS 27; the Mac has macOS 26.6.

## Measurements before choosing

Patrik's transactions are exported from the server to a folder on the MacBook outside every repo, used for the
measurements and never committed. The answer key comes from D7.

- **M1 — Starter rules:** what share of payments they sort, and how many of those correctly.
- **M2 — Learning from corrections:** replay Patrik's payments in date order as if he were a new user who fixes every
  wrong category; count the fixes needed (first month, first 100 payments, in total), with and without starter rules.
  This shows how much work a new user has.
- **M3 — Auto-sort:** on what M1 and M2 leave open: correct share and time per payment, on-device model vs Private
  Cloud Compute; which categories get mixed up.
- **M4 — Receipts:** 20–30 real receipts from different shops (REWE, Aldi, Lidl, Edeka, dm, Rossmann, a bakery, a
  restaurant), photographed by Patrik: items read correctly, totals that check out, items sorted correctly, seconds per
  receipt; whether the QR code is there and readable.
- **M5 — Engine test run (D1):** today's parsers and dashboard bundled into one JavaScript file and run in
  JavaScriptCore on the simulator, on the existing test files (`AresiumTests/server-dashboard.sample.json` and the
  server's expected answer). Identical output → one engine; problems → reconsider.

The results go into this file before the choices that depend on them.

## Order of work and rough size

Rough sizes in focused work days (Claude with Codex), not counting Patrik's time.

1. **Decisions D1–D8** (Patrik).
2. **Measuring bench, answer key, M1–M2** (Codex: export and replay scripts; Claude checks). 1–2 days.
3. **M5 engine test run**, then pull the engine out of the server into pure functions, with the server switching to it
   only after it gives identical numbers on the real data. 3–5 days.
4. **Phone mode:** storage, import of VR Bank / PayPal / CAMT on the phone, dashboard from the phone's engine, export,
   logout without deleting. Checked by importing Patrik's own files on the test account: the same numbers as
   aresium.de. 5–8 days.
5. **Categories you can edit, learned sorting, starter rules, more banks** (D5 first). 5–8 days.
6. **Auto-sort** after M3. 2–3 days.
7. **Receipts:** splits (server and phone), scanner, reading, checking, matching; M4 on real receipts. 6–10 days.
8. **Privacy policy, App Store information, external TestFlight, hub open.** 1–2 days, and Apple's approval of the
   developer account (pending since 2026-10-23).

In total roughly five to seven weeks of steady work. Steps 2–3 can start as soon as D1, D7 and D8 are answered.

## Sources

- Apple, WWDC26 "What's new in the Foundation Models framework" (session 241): image input to the on-device model,
  Private Cloud Compute for apps (no account, no keys, no prompts stored, free under 2 million first downloads, daily
  limits per user), `OCRTool`, `BarcodeReaderTool`. https://developer.apple.com/videos/play/wwdc2026/241/
- Apple, `RecognizeDocumentsRequest` (iOS 26; structured documents, tables and lists):
  https://developer.apple.com/documentation/vision/recognizedocumentsrequest and WWDC25 session 272.
- The Mac's own model on 2026-10-26: `SystemLanguageModel.default` → `appleIntelligenceNotEnabled`; supported
  languages include `de`.
