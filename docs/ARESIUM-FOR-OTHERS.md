# Aresium for other people — plan

**Draft 2026-10-26** (Claude, for Patrik); Patrik's answers the same evening (two rounds) are in "Decisions". Nothing here is built
yet. Measurements **M1–M5** come before the choices that depend on them. **Version 1 is the basics** (phone mode,
imports, categories, sorting); receipts are version 2 (Patrik, 2026-10-26). Server: `~/aresium`; app: `empire-ios/Aresium`.

## What it is

Aresium is Patrik's finance dashboard (aresium.de and the iPhone app): bank and PayPal exports go in, every payment
gets a category, and the app shows where the money goes by month and category. "For other people" means anyone Patrik
approves can use the app for their own money, with their data on their own iPhone.

## Already decided (Patrik)

- **Their data stays on their iPhone:** imports, categories, storage. No bank data on any server of ours. Patrik's own
  data stays on the server for aresium.de (2026-10-25; [PRIVACY.md](PRIVACY.md) → Facts, `empire-ios/CLAUDE.md` → Open 5).
- **A plan and tests first** (2026-10-25): imports from other banks; suggested categories people change and extend;
  sorting learned from their own corrections; auto-sort for the rest only if they switch it on (Apple's on-device
  model, or a server that stores nothing); each layer measured on Patrik's own transactions before choosing. Changed 2026-10-26: our server only, Groq, nothing stored (D2).
- **Receipts** (2026-10-26, new): take a photo of a receipt in the app; it adds it to the right payment and sorts the
  items into categories. **Version 2**, after the basics; no photos kept (Patrik, 2026-10-26).
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
- **Bank CSVs differ in layout:** column names and order, `;` or `,`, decimal commas, date formats, one amount column
  or separate debit/credit columns, account details in lines above the table, and the text encoding (many German bank
  CSVs are Windows-1252 / ISO-8859-1, not UTF-8; the app reads only UTF-8 today, which breaks umlauts).
- **Flexible reading, with AI only for the layout** (Patrik, 2026-10-26: no list of people or banks yet, so be
  flexible): the app finds the table and the encoding itself; known layouts are recognised by their header line; for
  an unknown one, an AI maps the **column names** to date, amount, text, counterparty and so on (the header line holds
  no one's payments, so nothing personal leaves the phone). The app then checks the mapping against the values (dates
  parse as dates, amounts as amounts), shows a preview of the first rows on the phone, the person confirms once, and
  the layout is saved on the phone for the next import. Where a bank offers CAMT, the app suggests it.
- **Order:** CAMT and MT940, then the common CSVs (Sparkasse, Volksbank, ING, DKB, comdirect, N26, Revolut, Trade
  Republic) as known layouts; PayPal exists; credit cards later.
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

Decided by Patrik (2026-10-26): **a solid list to choose from, nothing preselected.** On first start (and later in
Aresium's settings) a clear screen lists the default categories in groups; people tick the ones they want and type
names to add their own. Their list (defaults ticked plus their own) is what sorting uses, and what the app sends with
an auto-sort request.

- **The default list** (draft for Patrik's OK; each with an English and a German name, shown in the app's language, an
  icon and a colour; the kind decides how it counts):

  | Group | Categories (English · German) |
  |---|---|
  | Everyday | Groceries · Lebensmittel; Drugstore · Drogerie; Eating out · Essen gehen; Coffee & snacks · Kaffee & Snacks |
  | Home | Rent · Miete; Utilities · Nebenkosten; Internet & phone · Internet & Handy; Household · Haushalt; Pets · Haustiere |
  | Getting around | Bus & train · Bus & Bahn; Car & fuel · Auto & Tanken; Taxi & sharing · Taxi & Sharing; Travel · Reisen |
  | Health & care | Health · Gesundheit; Sports & fitness · Sport & Fitness; Personal care · Körperpflege |
  | Free time | Going out · Ausgehen; Entertainment · Unterhaltung; Hobbies · Hobbys; Subscriptions · Abos |
  | Shopping | Clothes · Kleidung; Electronics · Elektronik; Shopping · Shopping; Gifts · Geschenke |
  | Study & work | Education · Bildung; Work · Arbeit |
  | Money | Insurance · Versicherungen; Taxes · Steuern; Fees · Gebühren; Memberships · Mitgliedschaften; Donations · Spenden; Cash · Bargeld; Friends · Freunde; Savings & investing · Sparen & Anlegen (not counted as spending) |
  | Income | Salary & side jobs · Gehalt & Nebenjob; BAföG & scholarships · BAföG & Stipendium; Parents & family · Eltern & Familie; Kindergeld · Kindergeld; Selling things · Verkäufe; Interest & dividends · Zinsen & Dividenden; Other income · Sonstige Einnahmen |
  | Other | Other · Sonstiges |

- **Two built in, not on the list** (Claude's addition, for Patrik's OK): **Own transfers** (money between one's own
  accounts, never counted, so nothing is counted twice) and **Not sorted** (what nothing could sort yet, shown as a
  to-do). Money back under a spending category counts as a refund, as today.
- **Default categories follow the app's language** (stored by id); one's own keep the name as typed. Own categories
  get an icon and colour picked automatically, changeable later.
- **People change it later:** tick more, untick (its payments move to another category or to Not sorted), rename,
  merge, pick icon and colour. Icons and colours are stored per category, not fixed by name in code.
- **Splits** (version 2, with receipts): one payment divided into parts with their own category and amount.
- Flat list, as today (no subcategories). Patrik's own categories in server mode stay as they are.

### 5. Sorting: three layers

Every category shows where it came from (starter rule, learned, auto, you), as today's "via rule / llm / manual".

1. **Starter rules:** a list shipped with the app: common German merchants and patterns (REWE, Aldi, Lidl → Groceries;
   dm, Rossmann → Drugstore; DB, MVV, FlixBus → Bus & train; Spotify, Netflix → Subscriptions; salary and rent
   patterns). The same for everyone, updated with the app; a rule applies only when its category is on the person's
   list.
2. **Learned from their corrections:** when someone moves a payment to another category, the app remembers it for that
   merchant (the name cleaned of card numbers, cities and dates) and asks once: "Also the 12 other payments to
   REWE?". Future payments from that merchant follow. Own rules ("text contains …") as today. This layer should sort
   most payments, because a few merchants make up most of them (M2 checks this).
3. **Not in version 1** (D2 changed 2026-10-26, see Decisions). As first planned: **auto-sort through our server, one switch in Aresium's settings, off by default** (Patrik, 2026-10-26: easier,
   works on every iPhone, only a few friends will use it). For what layers 1 and 2 leave open:
   - The app sends the person's category list and the open payments (date, amount, text, counterparty; a random
     reference per payment, no bank ids) to a new Aresium route; the server asks the AI model, sends back one category
     per payment from that list (or none), and **stores nothing**: no database row, no request body in any log.
     Rate-limited per account; open to every account with the Aresium service, not only the owner list.
   - **The AI provider:** Groq, as today (`llama-3.3-70b` unless M3 finds a better one). Its documentation says it
     keeps no data from normal requests and keeps reliability and abuse logs for up to 30 days unless **Zero Data
     Retention** is switched on in its Data Controls (checked 2026-10-26, console.groq.com/docs/your-data). Switch it
     on before opening; Groq runs in the US, so the privacy policy names that transfer.
   - **Before opening:** the switch says in one sentence what it does ("Payments that Aresium cannot sort by itself are
     sent to our server and an AI to be sorted; nothing is stored"); the privacy policy explains it; the netcup
     processing agreement (AVV) is updated (it says "no financial data" today); Groq's data processing terms are
     accepted. Switching it on is the person's consent.
   - Apple's on-device model is not used (Patrik, 2026-10-26: our server is easier and works on every phone).

### 6. Receipts (version 2)

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

- Aresium's section in the privacy policy, in German and English: data on the phone; what auto-sort sends where (our
  server and Groq, nothing stored); the account. App Store privacy label: only the account (email) is collected; no financial data.
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
| 11 | **An answer key for measuring:** 191 payments were sorted by the Groq AI or not at all, never checked | Use the 1,055 known to be right (**D6**); the rest only if needed |
| 12 | **Widgets in phone mode** | They read the phone's snapshot as today; small change |
| 13 | **The website:** others have nothing on aresium.de | Say so on the site's login: "Aresium for others is the iPhone app" |
| 14 | **Leaving or deleting** removes the phone's data | After offering an export (part 2) |

## Decisions

Answered by Patrik on 2026-10-26:

- **D1 — How the phone gets the logic:** Patrik left it to Claude ("what makes the most sense overall"). **One
  engine:** today's TypeScript parsers, rules and dashboard become pure functions (no database, no Node-only parts);
  the server runs them in Node as now, and the app runs the same file in JavaScriptCore, Apple's built-in JavaScript
  engine (allowed in App Store apps when the code ships inside the app). Why: a fix or a new bank lands once, both
  places give the same numbers, and Patrik's server, website and scripts keep working. Rejected: a second copy in Swift
  (two copies that must stay identical, every change twice); moving Patrik to phone mode as well (one engine, but it
  changes his website imports, the Groq pass and the Telegram bot). **Condition:** M5 shows it runs fast enough on the
  phone (apps get JavaScriptCore without its fastest mode); if not, a Swift copy with shared test files. **Confirmed by M5 (2026-10-26).**
- **D2 — Auto-sort route:** our server only, with Groq (part 5, layer 3). One switch, off by default.
- **D3 — Categories:** a default list to choose from, nothing preselected, own names typed in (part 4).
- **D4 — Receipts:** version 2; photos not kept.
- **D5 — First people and banks:** not known yet → flexible reading, with AI on the column names for unknown layouts
  (part 3).
- **D6 — Answer key for measuring:** the categories known to be right: the 1,003 set by Patrik's own keyword rules and
  the 52 he set by hand (1,055 payments). The 123 the Groq pass set and the 68 without a category stay out; Patrik
  checks them later only if a larger test set is needed. This set suits a new user well: without Patrik's rules,
  auto-sort would see payments like these.

Patrik approved the default list (2026-10-26).

**D2 changed 2026-10-26 (Patrik: "makes sense"): version 1 has no server sorting.** After the legal check
(`PRIVACY.md` → "Opening Aresium: legal check", kept on branch `codex/03-aresium-privacy`) and M3: the server route needs
more than the AVV and the policy (Groq's contract and a transfer assessment for the USA, explicit consent for sensitive
booking texts, people named in booking texts, a record of processing, and possibly a DPIA, which in Germany would also
require a data protection officer, § 38 BDSG), while M3 shows it saves about 4 fixes a month. Version 1 sorts with the
shop rules, learning and the PayPal rule; nothing about payments leaves the phone, the AVV stays as it is, and the
policy's Aresium section says the data stays on the iPhone. Apple's on-device model can come later as the optional
switch. The Groq client stays in `aresium/src/sort/` (also usable for Patrik's own server).

## Measurements before choosing

Patrik's transactions are exported from the server to a folder on the MacBook outside every repo, used for the
measurements and never committed; only scripts tested on made-up data touch them, and only summary numbers are read
back. The answer key is D6 (1,055 payments).

- **M1 — Starter rules:** what share of payments they sort, and how many of those correctly.
- **M2 — Learning from corrections:** replay Patrik's payments in date order as if he were a new user who fixes every
  wrong category; count the fixes needed (first month, first 100 payments, in total), with and without starter rules.
  This shows how much work a new user has.
- **M3 — Auto-sort:** correct share, time and cost per payment for the server route (Groq), both for a new user
  (everything the starter rules leave open) and after learning (what M2 leaves open); which categories get mixed up;
  with the default list and with a short custom list.
- **Results M1–M3 (2026-10-26, on the server, 1,055 payments, 2025-09 to 2026-10; `aresium/bench`, results file kept
  off the repos):**
  - **M1:** the shipped shop rules sort 63.7% of payments on day one, 95.2% of them right (both scenarios).
  - **M2:** with shop rules plus learning from corrections, a new user fixes 12 payments in the first month, 14 in the
    first 100, 158 in all (15% of payments); from the second month on 86–99% of each month's payments get a category
    by themselves, 77–97% right. Learning alone, without the shop rules: 490 fixes. The shop rules cut the work by
    two thirds.
  - **M3 (Groq, `openai/gpt-oss-120b`; `llama-3.3-70b-versatile` is no longer available to the account):** on what
    the shop rules leave open for a new user, 31% right with Patrik's own list, 38% with the default list. In the
    monthly replay, Groq saves 60–63 fixes over 14 months (263 → 203), about 4 a month. About 1 s per payment;
    about $0.01 for all.
  - **M3 with NVIDIA (2026-10-27, `nvidia/nemotron-3-ultra-550b-a55b`, the best of the hub key's 85 models that
    answered; Kimi K2.6 404, GLM-5.3 and DeepSeek V4.1 timed out):** new user 18% (own list, 5 of 16 batches timed
    out) and 39% (default list) right; replay 263 → 226 and 263 → 206 fixes. Not better than Groq's gpt-oss-120b, slower
    and less reliable. What the shop rules leave open is mostly what only the person knows (money from parents, own
    tools, transfers), which no model can guess.
  - **After briefs 13, 16 and 17 (2026-10-27; the shop list of 2,815 names with directions and branch numbers, the
    structural rules for PayPal and own transfers, one sortPayments call over all payments):** day one 75.7% sorted,
    98.4% right; 315 payments (30%) found as own transfers, 100% right. A new user fixes **51 payments in 14 months**
    (was 158): 9 in the first month, 13 in the first 100, then about 3 a month. Learning alone would be 377. What stays
    unsorted on day one is personal (money from parents, own tools, private PayPal sellers).
  - **Main error source in all layers:** Patrik imports both his bank and his PayPal export, so the bank's PayPal lines
    are transfers for him (`isPaypalBankFunding` on the server), while their text names the shop ("Ihr Einkauf bei
    Vinted"); learning and the AI put them under the shop's category (Transfer → Clothes 68 times in M3). The engine
    needs the server's PayPal rule (a person who imports both: bank-side PayPal lines are own transfers). Measure
    again after it.
- **M4 — Receipts (version 2):** 20–30 real receipts from different shops (REWE, Aldi, Lidl, Edeka, dm, Rossmann, a bakery, a
  restaurant), photographed by Patrik: items read correctly, totals that check out, items sorted correctly, seconds per
  receipt; whether the QR code is there and readable.
- **M5 — Engine test run (D1):** today's parsers and dashboard bundled into one JavaScript file and run in
  JavaScriptCore on the simulator, on the existing test files (`AresiumTests/server-dashboard.sample.json` and the
  server's expected answer). Identical output → one engine; problems → reconsider.
  **Result (2026-10-26, `empire-ios/prompts/10-engine-test-run.md`):** identical output for the sample dashboard and
  all three readers (numbers and payment ids). iPhone 17 simulator, median of 5, with JavaScriptCore's fast mode off as
  on a phone: bundle load 3 ms; dashboard for 1,246 payments 5 ms, for 5,000 payments 11 ms; reading a 5,000-row VR
  Bank CSV 430 ms. Bundle 215 KB. A real iPhone is slower than the Mac behind the simulator; even several times slower
  is fine for an import. The engine lives in `aresium/src/engine/` (`npm run engine`); the hashing for payment ids no
  longer needs Node (same ids, checked).

The results go into this file before the choices that depend on them.

## Engine follow-ups (from briefs 12 and 14, 2026-10-27)

1. **Own transfers between accounts pair too easily:** equal opposite amounts within 3 days on two accounts can be
   unrelated (a 20.00 purchase and a friend's 20.00). Require the counterparty's IBAN to be the person's other account
   (the bank readers of brief 14 deliver IBANs), or leave the pair unsorted.
2. ~~**Income counts incoming own transfers**~~: fixed and live 2026-10-27 (Patrik agreed): transfer categories count
   as neither spending nor income; on Patrik's data total income 37,566 → 26,664, spending unchanged.
3. **The bench sorts one payment at a time,** so the new structural rules never run in it; switch it to one
   `sortPayments` call over all payments, then measure M1–M2 again (also for the bigger shop list, brief 13).
4. **English PayPal exports:** their funding rows ("Bank Deposit to PP Account") are not left out yet; only the German
   wording is. Add it (Patrik's numbers do not change; check with the parity script idea).

**From brief 14 (bank readers, 2026-10-27):**

5. **ZIP files** (Sparkasse sends CAMT as a ZIP) and Excel files are not read; the app has to unzip first (iOS has no
   ZIP API in Foundation: a small reader in the app, or ask the person to unzip).
6. **PayPal's tab-separated export** is not handled.
7. **The same period as CSV and as CAMT** still gives different ids (duplicates); not solved yet.
8. Santander/Openbank, Advanzia, Hanseatic and the Targobank credit card have no public header: their files go to the
   layout guess. Changing a profile's columns later changes its ids, so profiles change with care.

**From brief 13 (shop list, 2026-10-27):** 288 → 2,815 names. Measured on Patrik's payments: share sorted unchanged
(64%; his leftovers are personal), share right 95.2% → 93.8%, mostly the PayPal double import (handled by the
structural rule once the bench runs it, brief 16) plus two real weaknesses fixed in brief 17 (direction of the money,
branch numbers). Licence: name-suggestion-index is BSD-3-Clause; its notice goes on the apps' Fonts & licences page
(after brief 15 merges).

## Progress (2026-10-27)

Built and merged, all by Claude agents (Patrik, 2026-10-27), each checked by Claude:
- The engine: dashboard source, PayPal and own-transfer rules (parity on the real data: identical), `/api/mode` (live),
  25 bank layouts plus CAMT/MT940 and a guessed layout for unknown CSVs, the default categories with their look, 2,815
  known shops with directions and branch numbers (M1 98.4% right, M2 51 fixes in 14 months).
- Income without own transfers (live on aresium.de, Patrik agreed).
- The app's phone mode (brief 15): the engine in JavaScriptCore, storage per account, import, sorting, learning,
  categories, export/restore, the data lifecycle; server mode unchanged.
- Running: brief 18, the look of the new screens and their German.

Left before friends get it: brief 18; the privacy policy's Aresium section (phone-only text, PRIVACY.md → To do 6);
Apple's approval and external TestFlight (Apple reviews it); hub catalog `open`. Known limits to decide later: an
account deleted from another app leaves Aresium's store on that iPhone (only Aresium can delete it); offering an export
before leaving; ZIP files.

## Order of work and rough size

Rough sizes in focused work days (Claude with Codex), not counting Patrik's time.

1. ~~**Decisions D1–D6**~~ (Patrik, 2026-10-26); the default list waits for his OK.
2. **Measuring bench, answer key, M1–M2** (Codex: export and replay scripts; Claude checks). 1–2 days.
3. **M5 engine test run**, then pull the engine out of the server into pure functions, with the server switching to it
   only after it gives identical numbers on the real data. 3–5 days.
4. **Phone mode:** storage, import of VR Bank / PayPal / CAMT on the phone, dashboard from the phone's engine, export,
   logout without deleting. Checked by importing Patrik's own files on the test account: the same numbers as
   aresium.de. 5–8 days.
5. **Categories you can edit, learned sorting, starter rules, flexible bank reading** (part 3). 5–8 days.
6. **Auto-sort** after M3. 2–3 days.
7. **Privacy policy (including the auto-sort route), App Store information, external TestFlight, hub open.** 1–2
   days, and Apple's approval of the developer account (pending since 2026-10-23).

Version 1 in total: roughly four to five weeks of steady work. M5 done (one engine confirmed); M1–M3 can start now.

**Version 2: receipts** (part 6): splits (server and phone), scanner, reading, checking, matching; M4 on real
receipts. About 6–10 days.

## Sources

- Apple, WWDC26 "What's new in the Foundation Models framework" (session 241): image input to the on-device model,
  Private Cloud Compute for apps (no account, no keys, no prompts stored, free under 2 million first downloads, daily
  limits per user), `OCRTool`, `BarcodeReaderTool`. https://developer.apple.com/videos/play/wwdc2026/241/
- Apple, `RecognizeDocumentsRequest` (iOS 26; structured documents, tables and lists):
  https://developer.apple.com/documentation/vision/recognizedocumentsrequest and WWDC25 session 272.
- The Mac's own model on 2026-10-26: `SystemLanguageModel.default` → `appleIntelligenceNotEnabled`; supported
  languages include `de`.
