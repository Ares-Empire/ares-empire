# ARES EMPIRE — the living charter

The central hub / home of the empire — one throne that ties together every "Ares"
service. This file is the **always-active empire doc**: the canonical, human-readable
source of truth for the vision, the design language, the provinces (projects), the
expansions (ideas) and the chronicle (what was done to conquer what).

Its machine twin is [`web/app/empire-data.js`](web/app/empire-data.js) (`window.EMPIRE`) —
the manifest the hub website actually renders from. **Keep the two in step.** When a
province is added or its state changes, update *both* this file and the manifest.

> On the name: "Ares" is Patrik's long-standing handle. The war-god association is
> treated as *aesthetic* — marble, gold, command, gravitas — never devotional.

## Now and next (updated 2026-10-29)

**Where things stand:** five iPhone apps (Empire, Aresium, Arestemis, Aresus, Arestoteles) run on the simulator, all
on the shared standard (Settings, English/German with an in-app switch, light and dark, one Ares account run from every
app). The Empire app was reviewed before its first TestFlight build (council 2026-10-25, fixes live); its ring shows
every app an account has and "+" asks for more ([docs/EMPIRE-APP.md](docs/EMPIRE-APP.md)). The privacy policy and
imprint are live and linked from every site, the websites load nothing from other hosts, and the data that cannot be
rebuilt is backed up every night to the MacBook ([docs/BACKUP.md](docs/BACKUP.md)). Showcase images of every app with
made-up data: `empire-ios/showcase/`. Apple approved the developer account on 2026-10-29 (team `WQN8SHAH9B`): Aresium
is on Patrik's iPhone through internal TestFlight. The comfort items Patrik approved for the other four apps are built
(2026-10-30, briefs 49–52), the push key is live, and Arestemis is on Patrik's iPhone (push works there, its Telegram copy is off since 2026-10-31); Aresus (with Aresync) was uploaded on 2026-10-31; Arestoteles and the
Empire app were uploaded on 2026-11-01 (Arestoteles with its bust free of the watermark, everywhere), so all five apps
reach Patrik's iPhone through internal TestFlight.

**Next up (2026-10-27):** Aresium for other people is built (phone mode: their data on their iPhone, 25 banks, 2,815
known shops, no AI; [docs/ARESIUM-FOR-OTHERS.md](docs/ARESIUM-FOR-OTHERS.md) → Progress). Privacy policy section live
(2026-10-27). The payment page in plain words and import-first are
merged (briefs 27–28). On Patrik's iPhone since 2026-10-29 (internal TestFlight). Before friends get it: external TestFlight, which Apple reviews; friends get the TestFlight link directly (no account, no hub step).

**The big steps, in this order** (Patrik, 2026-10-25):

1. ~~**Light mode**~~ done 2026-10-25 for all five apps ([IPHONE-APPS.md](docs/IPHONE-APPS.md) → Every app has;
   `empire-ios/CLAUDE.md` → Light mode). Left for the phone: both looks checked once TestFlight runs.
2. **TestFlight** as soon as Apple approves: the signing team, App Store Connect records, upload, then push
   notifications (APNs key) and retiring Telegram (`empire-ios/CLAUDE.md` → Open 1–3 and 6;
   `empire-ios/docs/APP-STORE.md` for the forms). The builds go only to Patrik (internal testing: no Apple review).
   Apple reviews an app only when it goes to other people (App Store or external testers); its demo account then gets
   an extra address on Patrik's domain. Aresus and Aresync stay Patrik's own tools and never go to others (Patrik,
   2026-10-25).
3. **Aresium for other people:** their data stays on their iPhone (imports, categories, storage); no bank data on the
   server. Its section goes into the privacy policy before it opens ([PRIVACY.md](docs/PRIVACY.md) → the rule).
   Needs a plan and tests first (Patrik, 2026-10-25): imports from other banks; suggested categories that people
   change and extend; sorting learned from their own corrections; auto-sort for the rest only if they switch it on
   (Apple's on-device model or the server without storing anything, to be decided); each layer measured on Patrik's
   own transactions before choosing. Also receipts from a photo (Patrik, 2026-10-26). Plan:
   [docs/ARESIUM-FOR-OTHERS.md](docs/ARESIUM-FOR-OTHERS.md).
4. **Aresync file sharing from the phone:** Patrik's idea (2026-10-25), specified 2026-11-01: send any file or photo
   from the iPhone to a chosen folder on the MacBook (Documents or Downloads, else `Zu sortieren`), receipts into
   Rechnungen with their inventory line. Plan: [docs/ARESYNC-DROP.md](docs/ARESYNC-DROP.md).
5. **New apps**, each built on the standard from its first screen.

**Smaller open items:** the rest is in `empire-ios/CLAUDE.md` → Open and
[PRIVACY.md](docs/PRIVACY.md) → To do.

---

## The crown language (design system)

Inherited from Aresium + Arestoteles and elevated to the crown:

| | |
|---|---|
| **Palette** | Near-black wall · **polished gold**, used sparingly as an accent (not glare) · off-white. Lit by faint **Mars-red + steel-blue** ambient. |
| **Type** | Space Grotesk (text + caps labels) · JetBrains Mono (numbers/code). Clean and modern — no serif. |
| **Surfaces** | Glassmorphism (blurred translucent cards with a bright gradient edge), tight letter-spacing, restrained motion. |
| **Figure** | A **monochrome marble bust** (`brand/head1.png`) stands flush at the **left edge**, blended into the wall (screen-blend + edge mask), gazing toward the circle. |
| **Crown mark** | The **Ares bust in gilded war-gear** (`brand/ares-bust.png`) — the intro's slamming figure + the favicon. |
| **Signature motion** | The **slam intro**: the bust drops; fine gold fissures burst from the root **all at once** and grow outward; "ARES EMPIRE" slams in in polished gold with a single shine. |

Gold is the **one premium accent** (the `.ares-word` / `--gold-text` metallic text-clip) —
province names, titles, timeline nodes — over an otherwise black, modern field. No persistent wordmark.

---

## How we build apps (web + iOS)

Every province may get a website and an iPhone app ([docs/IPHONE-APPS.md](docs/IPHONE-APPS.md)).
**A good structure is worth more work now.** (Patrik, 2026-10-23.)

When the quick way (adding code wherever it fits, a workaround, copying a calculation into a second place)
would make later changes slower or cause bugs, choose the better structure instead, even if it takes longer
now or means partly rebuilding something that already works. Saving work today that causes more work later
is the wrong saving.

This is judgment, not a rule to merge or share things. Separate pieces are fine when they are simpler. The
question each time: which structure leaves less work and fewer problems over the coming months?

Example: Aresium's website calculates its numbers in the browser. An iPhone app would have to copy those
calculations, so they move to the server first ([IPHONE-APPS.md](docs/IPHONE-APPS.md), step 3).

When restructuring: go in steps that keep the live service working; before switching, show that the new
version gives the same results as the old one; then delete the old code. When the better structure is much
bigger than the task at hand, tell Patrik what, why and roughly how big before starting.

**Every app speaks English and German** (Patrik, 2026-10-24), the current ones and every future one: the iPhone's
language decides, English is the fallback. Interface text is translated, including the sentences servers write for the
apps and the notifications; content people wrote is not. Rules: [docs/LANGUAGES.md](docs/LANGUAGES.md).

**Data that cannot be rebuilt is backed up every night** (Patrik, 2026-10-25): a service that starts storing such
data adds it to the nightly backup in the same change ([docs/BACKUP.md](docs/BACKUP.md) → New data).

**A website's light or dark travels with its links** (Patrik, 2026-11-01 and 2026-11-07): a link to another Empire
site that reads it passes `?look=light` or `?look=dark`, and that page opens in it for the visit without remembering
it. patrikbreeck.com passes its look; the hub, which is always dark, passes `dark` (`web/app/empire-api.js` →
`passLook`, the legal pages' contact links); the Arestemis demo passes the look it shows to its request form. Pages
that read it: aresium.de, arestemis.de and the hub's contact pages. A new site with light and dark reads it too.

**Councils check the big choices** (Patrik, 2026-11-05): a few agents, each with its own role and question, look at a
plan or a piece of work blind, then check each other's answers, and Claude brings Patrik one verdict. Used for choices
that are hard to undo, milestones, a bug that comes back, and an expansion before it gets a plan. Method and roles:
[docs/COUNCIL.md](docs/COUNCIL.md). When Patrik says "council", this is what he means.

---

## The hub (what the website is)

A single full-screen scene — clean, modern, mostly black with gold accents:

- **Intro (first visit / per session):** the slam (above), then it **morphs** straight into the hub.
- **Left edge:** the marble bust (`head1.png`), embedded into the wall, gazing toward the circle.
- **Top:** the centered section title — **PROJECTS** or **EXPANSIONS** — with an **EXPAND** toggle
  and a **logout** button on the right.
- **Center-right:** the **orbital circle** — a stretched, offset ellipse the provinces ride as
  horizontal tabs (mark · GOLD NAME · status). Drag / scroll / ← → to revolve; click the focused
  one to spread the circle into the **project board** (count-adaptive: 2 → L/R, 3 → L/M/R,
  4 → quadrants …) with context under each.
- **Below the circle:** the **chronicle**, as a clean horizontal **timeline**.
- **EXPAND → EXPANSIONS:** the plans on the same board; open one (or **Claim new ground**) → the CONQUER forge.

What the live hub and the Empire app show comes from the server's `/root/ares-empire/data/state.json`, not from
this repo. A province marked `"lock": true` there (Aresium, Arestoteles, Arestemis) is written by hand and the nightly
`empire_sync` skips it: when its text in `web/app/empire-data.js` changes, change it in `state.json` too (back it up
first). An empty `changelog` shows the province's chronicle entries, as the Empire app always does.

---

## Provinces (the project registry)

Mirror of `EMPIRE.projects`. Status vocabulary: `SCOUTED` (idea) → `BESIEGING` (WIP) →
`CONQUERED` (live & held) → `FORTIFYING` (live, maintenance).

| Province | State | Domain | What it is |
|---|---|---|---|
| **Aresium** | CONQUERED | aresium.de | Personal finance from your bank's own exports — imported, sorted and understood; a website and an iPhone app. |
| **Arestoteles** | CONQUERED | arestoteles.de | Patrik's Weltbild on the phone — positions, topics, mechanisms, events; read, search, edit, discuss with Claude. |
| **Arestemis** | CONQUERED | arestemis.de (its demo) | Searches that run for you — flats, things for sale, prices and web pages; an iPhone app, every find checked by an AI, a push when one fits. |
| **Aresync** | BESIEGING | — | Git sync across Windows & Mac — every repo, everywhere, automatically. |
| **Arescope** | BESIEGING | — | Personal exposure scanner — searches public sources for your own name, emails and photos, an AI rates each finding, fixes are proposed. Works in parts; no phone app planned (2026-10-24). |

---

## Connections

Which provinces use the **Empire login** ([docs/ACCOUNTS.md](docs/ACCOUNTS.md)) and which have an
**iPhone app** ([docs/IPHONE-APPS.md](docs/IPHONE-APPS.md)). Every project keeps its own repo and
folder; being "part of the empire" is tracked here, not by moving folders (aresync clones every
repo as a top-level folder, and live services and data volumes depend on their paths).

| Province | Login | iPhone app | Repo |
|---|---|---|---|
| **Aresium** | **Empire login** (website, hub hand-off and API for the app) | **on Patrik's iPhone** (internal TestFlight, 2026-10-29) | `aresium` |
| **Arestemis** | **Empire login** (API for the app; its demo at arestemis.de) | **on Patrik's iPhone** (internal TestFlight, 2026-10-31): [docs/ARESTEMIS-APP.md](docs/ARESTEMIS-APP.md) | `Arestemis` |
| **Aresus** (+ Aresync) | **Empire login** (API for the app, no website; Aresync reports with machine tokens) | **on Patrik's iPhone** (internal TestFlight, 2026-10-31): [docs/ARESUS-APP.md](docs/ARESUS-APP.md) | `aresus`, `aresync` |
| **Arestoteles** | **Empire login** (API for the app); the website keeps its own login | **on TestFlight** (internal, 2026-11-01): [docs/ARESTOTELES-APP.md](docs/ARESTOTELES-APP.md) | `Arestoteles`, vault `carlsenares/opinions` |
| **Ares Empire** (hub) | **Empire login** — sign-up, approval and password reset live here; the push service for all apps ([docs/PUSH.md](docs/PUSH.md)) | **on TestFlight** (internal, 2026-11-01): [docs/EMPIRE-APP.md](docs/EMPIRE-APP.md) | `ares-empire` |

All empire repos live in the GitHub organization **[Ares-Empire](https://github.com/Ares-Empire)**
(aresync follows once every laptop runs the org-aware version). Each repo keeps its own
visibility. **Public since 2026-11-02:** `aresium`, `empire-ios`, `ares-empire`, `Arestoteles`, `ares` and `AresOS`, as fresh
repos with cleaned history (the old ones are private archives, `<name>-archive-2026-11`). Private: `Arestemis` (its
sites research and server briefs stay there), `aresus`, `aresync`, `arescope` and `companions` (until it is shown).
Public repos hold no personal data ([PRIVACY.md](docs/PRIVACY.md) → Owner file) and never say how
Arestemis gets past a site's blocks.

iPhone apps for every province live in one repo, **`empire-ios`** (name deliberately not
`ares…`, so the empire sync doesn't list it as a province of its own).

---

## Expansions (future plans)

Mirror of `EMPIRE.ideas` — the **EXPAND** view. Open one from the board and it pre-fills the CONQUER forge.

- **Empire accounts** — one account for every service and app: sign up with email + password, Patrik approves, every province trusts the login. Plan: [docs/ACCOUNTS.md](docs/ACCOUNTS.md).
- **iPhone apps** — real native apps installed via TestFlight, starting with Aresium, then widgets. Plan: [docs/IPHONE-APPS.md](docs/IPHONE-APPS.md).
- **Aresgora** — a public agora: the empire's outward-facing landing for the usable services.
- **The Council** — open work and Patrik's decisions in one place, so nothing waits unnoticed once a session moves on. A scan of every repo finds work that was built but never merged or shipped; sessions name themselves by topic, and open work goes to its topic's session, not to Patrik. Only what needs his own decision or action reaches him, in Aresus's "Waiting on you" tab: one tap answers, or opens the session that asked. Planned by two councils (2026-11-03, 2026-11-05: [record](docs/reviews/2026-11-05-work-board.md)); building since 2026-11-06.

---

## The conquest loop (how a province is born)

The hub is the **display + intent**; Claude Code (or a tiny local companion) is the **hands**
— a browser can't create directories or `git init` on your machine, so the forge hands off.

1. On the hub, hit **EXPAND** → open a plan card (or **Claim new ground**). Set the **name** + a one-line blurb.
2. The forge produces three things with copy buttons:
   - the new province's seed **`CLAUDE.md`**,
   - its **manifest entry** for `web/app/empire-data.js`,
   - a **handoff command** to paste into Claude Code.
3. Run the handoff in Claude Code → it scaffolds `projects/<slug>/`, drops the seed
   `CLAUDE.md`, appends the province to the manifest + a line to this Chronicle, and
   `git init`s. The new province takes its place in the circle.
4. (Optional, later) a local `POST /api/conquer` companion does step 3 on one button.

**There is always an active empire doc:** this file + the manifest. Claude Code reads them
to know the empire's shape, and appends to the **Chronicle** below whenever it conquers.

---

## The Chronicle (what was done to conquer what)

Newest first. Mirror of `EMPIRE.chronicle`; Claude Code appends here as it works
("did X to conquer Y"). The hub and the Empire app show the server's copy, `/root/ares-empire/data/state.json` →
`chronicle` on aresis, which a push does not update: add each new entry there too (at the top, same text).
After adding a line to `web/app/empire-data.js`, run `python3 tools/empire_samples.py --web` (the website's
previews are generated from it; a test checks they are current).

- **2026-11-07 · empire** — Every push now runs the tests. GitHub tests aresium, the hub, Arestoteles and the personal site's owner checks, and the five iPhone apps' unit tests on a simulator; the private services run theirs with one command on the MacBook. The first runs found two real faults (a test file that depended on the time zone, out-of-date hub previews). The iPhone tests no longer depend on how busy the machine is, and Release builds leave out the sample data, checked by a script before each upload.
- **2026-11-07 · aresium** — Aresium reads a Sparkasse's statements as they come, a ZIP of daily CAMT files, and Excel exports, without unzipping or converting first, and sorts a few more cafés, bars, clinics and bike shops by itself (10 fewer misses in the test set, none of Patrik's own payments changed). A review of the new reader by another session found that a crafted Excel file could exhaust the app's memory and that a ZIP could merge two look-alike payments; both were fixed before testers got it. Automatic import was researched: the banks' own FinTS interface can fetch transactions straight from the iPhone with no server in between, once the banking association registers Aresium and Apple's rules for individual developers are clear (aresium/docs/AUTO-IMPORT.md). Build 26 went to Apple's review for testers.
- **2026-11-07 · aresync** — A file sent from the iPhone that already reached the MacBook no longer shows as “Not sent”. A receipt had landed in Rechnungen, but the phone missed the server's confirmation, sent the file again a day later and took the server's refusal for a failure. Now the app asks the server before it sends a file a second time, and clears such leftovers by itself when it opens. Aresus build 10.
- **2026-11-06 · arestemis** — A search for things now asks what must be and what would be nice: “Muss sein” sorts out listings that clearly break it, “Wäre schön” never does. Sizes, colours and materials come from the sites' own fields, so a size-41 shoe no longer reaches a size-43 search, and clear cases are decided at once without the slower text check. Listings that could not be checked in time no longer vanish: they stay seven days under “Nicht rechtzeitig geprüft”. App build 23.
- **2026-11-06 · aresus** — The empire keeps its open work in one place now. A scan of every repo finds work that was built but never merged or shipped; Claude sessions name themselves by topic and hand open work to the session on that topic; and only questions that need Patrik reach him, in Aresus's new “For you” tab, where one tap answers. Aresus build 9.
- **2026-11-05 · arestemis** — After the first day of test searches: notifications are short (the listing's own title, not the reasoning behind it); saving a search for things suggests a correction when a brand looks misspelled (“Meintest du „Zegna Krawatte“?”); a watch on a page that only links to the thing offers the thing's own page; a Preismonitor “Überall” saves at once and finds the product in the background, with a push only when nothing fits; “Gespeichert” became Favoriten with a star on each listing; an opened listing counts as read; and the app's own requests now come before background checks. App builds 19 and 20.
- **2026-11-05 · arestemis** — Tapping a notification no longer crashes the app. The crash reports Patrik shared from TestFlight showed it: the app told iOS it was done with the tap from a background thread, which iOS answers by closing the app. The same fix reaches Aresus and Aresium. Arestemis build 21, Aresus build 8, Aresium build 24.
- **2026-11-05 · arestemis** — An opened listing now leaves “Neu” (Patrik: “It should leave neu”). “Zuletzt angesehen” keeps the ones opened in the last seven days that were not favourited, the latest first; to keep one longer, it goes into Favoriten. App build 22.
- **2026-11-05 · arestemis** — Arestemis's Preismonitor reads shipping costs on more sites now, so most offers compare by their real total; a price that only holds with a coupon counts at its normal price; and an offer whose shipping a shop does not state is no longer hidden: it shows in price order with “+ Versand unbekannt”, and its alarm says so, while the price curve keeps only known totals. App build 18.
- **2026-11-04 · arestemis** — Arestemis's Preismonitor “Überall” got its second round: every offer is checked to be the product itself, so a case never counts as the headphones' price; words that name a family or a kind of product get up to four concrete suggestions or a way to a search for things; the monitor compares the price including shipping, or finds stores near a chosen place for pickup; and “Auch gebraucht” adds used listings from marketplaces to the same page. A Codex orchestrator built and tested every step live on the real sites, the app's screens included. App build 17.
- **2026-11-04 · arestemis** — The Preismonitor can watch a product everywhere now (“Überall”): type a product such as AirPods Max 2, and optionally a colour or size in words, and within seconds Arestemis finds it on price comparison sites, shops and marketplaces, shows the cheapest offer with its shop and every shop's price, keeps the cheapest price as a curve and sends a push when it falls under a chosen price. A list shows every site it checks, each with a switch, and a button suggests a shop that is missing. Thing searches also got more accurate after a check of 747 real listings: a complete article sold with extras, another name or language for the same thing, and a shipped offer from far away are no longer turned down by mistake. App build 16.
- **2026-11-03 · arestemis** — One Arestemis search can now look for several similar things: up to five search words, such as ties from three makers, each read on every chosen site, with one description of what fits per word and one list of results. Behind it, every site is now read three ways (the page's own data, its layout, its plain text), so a site that changes its layout no longer silently loses a listing's facts; a check per site alerts within the hour if it does, and an AI fills in facts that only the ad's text states. App build 15.
- **2026-11-04 · aresium** — Aresium reads Sparda-Bank: a tester asked for it, and all eleven Sparda-Banks now run on the same online banking as the Volksbanks, so their files are read like a VR bank's and the account is named Sparda-Bank. The "How do I get my file?" guide has its steps in German and English, and build 23 went to TestFlight for testers, who can now join through a public link.
- **2026-11-03 · aresium** — The Aresium website caught up with the iPhone app: fixed costs and the monthly average, money paid back, search, the day and name pages, renaming, changing many payments at once, going through what is not sorted name by name, and categories made where one is chosen, on desktop and phone, in English and German, and all of it in the demo. Checking the new version on the real data showed that the balance line had been wrong for weeks, on the website and in the app: on a day with several payments, whichever was stored last decided it, and two accounts were mixed into one number. It is now each account's balance at the end of the day, read from the chain of its bookings, added up.
- **2026-11-03 · arestemis** — Arestemis's listing pages read like listings now: the numbers a search asks about in one card, a dash where the listing does not say, a few short notes on what to check, and the site's button first, while the application text moved to a quiet button. Where a site shows only a preview of the text, the page says so instead of looking cut off. New search lost most of its words: one line and one example per kind. Underneath, the AI was measured on 168 hand-labelled cases from real hunts, so things are now checked by a smaller model, and page watches on shop lists no longer take another product's price for the watched one. App build 14.
- **2026-11-02 · empire** — The code of the Ares Empire is public on GitHub: Aresium, the iPhone apps, the hub, Arestoteles and patrikbreeck.com, each a fresh repo whose history holds no personal data (name, address and email come from one file outside the repos, and the privacy check now lets commits that remove such data through). Arestemis, Aresus and Aresync stay private; the old repos are kept as private archives.
- **2026-11-02 · aresium** — Aresium now says what a month costs on average and how much of it is fixed: under the overview's total, the average of the finished months and the fixed part, which opens the fixed costs (rent, subscriptions, insurance), each found by its amount, how often it comes and a steady day, with when the next one is due; a cancelled subscription moves to Ended, and one counted by mistake is taken out with a long press. The income side shows regular money in the same way. Aresium also went to Apple's beta review for testers outside the empire, and a walk through a fresh install fixed three snags for newcomers first: skipping the category list left everything unsorted, the first days of a month showed almost nothing, and a German button read like 'delete'. Build 19 went to the phone through TestFlight.
- **2026-11-02 · arestemis** — Arestemis explains itself now: a tour of eight steps, shown once after the first login and again from Settings, walks through sample searches in the app's own language, from starting a search to what a Preismonitor and a page watch are for. Patrik asked for it when "Webseite beobachten" read as too vague; the tour's frame is shared with Aresium's, whose tour looks exactly as before. App build 13.
- **2026-11-02 · aresync** — Aresync carries files from the iPhone to the MacBook from anywhere: in Aresus's Aresync tab a photo, a camera picture or any file is sent with a folder in Documents or Downloads chosen on the phone (a new one can be made there, or Sort later) and a name. The server encrypts it on arrival with a key whose secret half only the MacBook holds; the Mac's own program fetches it within a minute while the Mac is awake, puts it in place without overwriting anything, and a quiet push says it was delivered. The first file from the phone landed on 2026-11-02 (Aresus builds 2 and 3); sent files are deleted from the list with a swipe as in Mail. Aresus in the iPhone's share sheet comes next.
- **2026-11-02 · arestemis** — Arestemis has a fourth kind of search, the Preismonitor: one product in one shop, its price kept as a curve over 30, 90 or 365 days, a push when it falls under a chosen price or is back in stock, or both, switchable at any time on the monitor's page. It reads the shop's own product data first and asks the AI only where a page has none. New search became a page of four cards with examples, and every search can be renamed in place without starting it again. App builds 11 and 12.
- **2026-11-02 · aresium** — Aresium links money paid back for several payments at once: select the expenses someone paid back, tick the payments that came in from them, and the money is shared out expense by expense, the oldest first, each paid back in full before the next, until it runs out; or the other way round, several transfers paying back one expense. Before linking, a summary shows what each expense gets back and what stays open or still counts as income, and one undo takes every link back. A payment that came in can never pay back more than it brought. Build 18 went to the phone through TestFlight.
- **2026-11-02 · aresium** — Bank files reach Aresium from anywhere now: shared from Files, Safari or AirDrop it opens and imports them, and a file dragged from Files onto its main screen is imported the same way, held until the lock opens. Watching the share sheet end to end for the first time found two bugs, both fixed: iOS's copy of a shared bank file was never deleted after reading, and an MT940 statement shared while Aresium was closed was refused. Build 17 went to the phone through TestFlight.
- **2026-11-02 · aresium** — Aresium can take money paid back off what was spent: when someone pays back an expense, all of it or a share, the two payments are linked by hand on either payment's page (suggestions first: the same amount, half, a third, within days; a search for paybacks in parts), and only one's own share counts as spent, in the expense's month and category, while the payback no longer counts as income. Nothing is matched without asking, and every other payment still counts as it happened. Patrik asked after Aresium's overview looked far too high. Build 16 went to the phone through TestFlight.
- **2026-11-02 · arestemis** — Arestemis can watch a web page now: give it an address and say in your own words what to look for ("when KALLAX costs under 45 €", "when the Mensa has Schnitzel"), and it reads the page every 15 minutes to once a day and tells you when it happens. Only a change goes to the AI, a list that merely reorders is no change, and a page that refuses the server is shown as stopped rather than knocked on again; pages of the sites it hunts and anything inside the server's own network are refused. It was tried on 17 real pages first. eBay went live the same afternoon with its own keys, and the app's Angebote tab now shows what is new grouped by search, and each search's listings on their own, with a search over all found listings, best match first. App builds 9 and 10.
- **2026-11-02 · aresium** — Selecting payments in Aresium works like Mail now: a finger sliding down the circles ticks every payment it passes and unticks them again on the way back, and held near the top or bottom the list scrolls on by itself. Selecting also became calm: a recording showed the bounce Patrik felt (each tick slid its circle in from the side and the count rolled letter by letter), so a tick now simply appears. Build 15 went to the phone through TestFlight.
- **2026-11-02 · aresium** — Aresium can go through what is not sorted name by name: after an import it offers to show the unsorted payments grouped by who they are with, the most payments first, and one tap on a category sorts all of a name's payments at once and teaches Aresium the name for the next import. Money in and money out of the same person are separate cards, skip and undo are always there, and nothing already sorted is touched. Not sorted's list starts with the same offer. Build 14 went to the phone through TestFlight.
- **2026-11-02 · arestemis** — Arestemis hunts on five sites for things now: besides Kleinanzeigen and MTB-News Bikemarkt it reads mydealz's deals, IKEA Preowned (used IKEA furniture near the search's towns, which OpenStreetMap now gives coordinates) and Vinted. Each was tested with a real hunt: Kallax shelves near Garching with the accessories filtered out, Levi's 501 on Vinted with brand, size and the buyer-protection fee. The app greys a site that cannot serve the chosen delivery (IKEA only for pickup, Vinted and mydealz only shipped). App build 8.
- **2026-11-02 · arestemis** — Arestemis became a hunter for more than flats: an account can run several hunts, and a new kind of hunt looks for things for sale on Kleinanzeigen (search words, words to leave out, a price with an allowance for negotiable prices, condition, pickup near a place or shipping, private sellers). The AI check filters out spare parts and accessories and warns of signs of a scam; a new hunt checks what is online once, quietly. Things are read every 3 minutes and each site has an hourly budget, so the flat hunt keeps its pace. Underneath, the server was split into a shared hunting core and one search type per kind, proven to find exactly the same flats before and after. App build 6.
- **2026-11-01 · aresium** — Aresium knows Germany's local places: a list of 264,744 shops, restaurants, cafés, practices and other places from OpenStreetMap sorts a payment at a place it knows into its kind, packed so it costs the iPhone about 13 MB (as plain data it took 103 MB, measured and refused first). With a third round of sorting fixes, a new person with Patrik's files now finds 984 of 1,246 payments sorted on day one and needs 103 corrections over 14 months instead of 111. The list can be downloaded at aresium.de/osm under the ODbL. Build 13 went to the phone through TestFlight.
- **2026-11-01 · empire** — The Ares Empire and Arestemis got contact pages like Aresium's: www.ares-empire.de/contact (German /kontakt) replaces the hub's old form and stays the Empire's general contact, and www.ares-empire.de/arestemis/contact is Arestemis's own. Each is one form for asking for the iPhone app and for questions, problems and ideas, in the app's own look, light or dark, in words that address no one, and both share one form with Aresium's. patrikbreeck.com and the hub's demo now ask for each app on its own page.
- **2026-11-01 · aresium** — Aresium can now change many payments at once: a circle in a category's list ticks payments as in Mail, and Kategorie or Name moves, adds to or renames all of them with one question for their shops and an undo. Saving an added category now asks whether to leave the old one and whether the shop's other payments should get it too. Build 12 went to the phone through TestFlight, with the first round of sorting and reading fixes.
- **2026-11-01 · aresium** — Aresium now measures how well it reads bank files and sorts payments, with test sets of 228 hard bank files and 2,039 invented payments whose right answers two independent AI judges set without seeing each other. The first round of fixes found against them: sorting leaves far less unsorted (missed 304 to 135, wrong 21 to 4, and as well on the held-back part nobody looked at), and no test file is read wrong any more (40 silent errors to 0). A category name that exists is now used instead of refused (Freunde for income too), and categories can be renamed and deleted, their payments sorted again. Build 11 went to the phone through TestFlight.
- **2026-11-01 · aresium** — Aresium can search: a magnifying glass finds a name, your own or the bank's, best match first, and opens all its payments. A tap on a day of the graph opens that day's spending and income, side by side to swipe. A shop now shows one name even when its bank line changed over the year (Vinted, Apple), and unsorted money in reads Nicht sortiert. Build 10 went to the phone through TestFlight.
- **2026-11-01 · arestoteles** — Arestoteles on the phone, its first evening: a note now closes the moment it is saved and goes to the vault's Inbox in the background, also when the app is left right away; a note that cannot be sent waits on the phone and the tabs say so. The vault is unpacked and indexed away from the screen's work, so the app no longer stalls when the vault loads or after an edit. Build 2 went to the phone through TestFlight.
- **2026-11-01 · empire** — The Empire app was uploaded to TestFlight for Patrik's iPhone, so all five Empire apps now reach his phone. A check of everything that differs between the simulator and a real iPhone found nothing in the way.
- **2026-11-01 · arestoteles** — Arestoteles was uploaded to TestFlight for Patrik's iPhone. Its Aristotle lost the watermark an image tool had printed across the face: the app icon, the app, arestoteles.de and the hub's ring now show the hub's clean bust. When the app drops its saved notes after a logout in another Ares app, they now leave iPhone search too, and its copy of the vault stays out of the iPhone's backups, since it can always be downloaded again.
- **2026-11-01 · aresium** — Aresium lets every category have a side: one's own categories now work for money in too, and a spending category that also gets money back (Freunde, when a friend pays back) can be offered for money in from the change window, without cluttering the menus. Every payment now counts once, as it happened: money out as Ausgaben, money in as Einnahmen, each under its own category. Build 9 went to the phone through TestFlight.
- **2026-11-01 · arestemis** — Arestemis now searches ImmoScout24, Germany's biggest flat portal, in every town, and Immowelt in every town it knows instead of only München. Kleinanzeigen changed its list pages on the evening of 31 October; Arestemis missed its new listings for part of the evening until the fix went live. In Settings, Bewerbung became three rows like the others: a switch for automatic texts, a page with one's own text or with notes every automatic text includes, and About you; the automatic text is now written from the facts about the person and those notes. Build 3 went to the phone through TestFlight.
- **2026-10-31 · aresus** — Aresus, with its Aresync tab, was uploaded to TestFlight for Patrik's iPhone. It now also watches each of Arestemis's search portals and tells only Patrik when one is blocked or failing: only after an hour without a break, as a normal notification that does not break through Focus, and silently if it comes back within six hours; the "running again" note replaces the alert. Short blocks no longer send anything, and a crash during such a problem still alerts at once. The false alarm about Aresium's retired Telegram bot is gone.
- **2026-10-31 · aresium** — Aresium makes a new category where one is chosen: the window that changes a payment's category, the receipt window and Bargeld eintragen offer "Neue Kategorie". The name is typed once, the category gets its own icon and colour and is already picked, so a payment no longer needs a detour through Settings. Build 8 went to the phone through TestFlight.
- **2026-10-31 · aresium** — Aresium after its fifth round on Patrik's iPhone: a payment's day reads as a date ("4."), a name's months open as pages of their own, Settings no longer stalls, and the add-up icon always means all or none in its list. The graph is read by holding a finger on it and sliding, a tap opens that month, and it moves away while the categories scroll (a switch in Settings); the header's buttons lost their boxes. The tour now walks through all of it in 18 steps. Builds 6 and 7 went to the phone through TestFlight.
- **2026-10-31 · aresium** — Aresium got its own contact page at aresium.de/contact (German: /kontakt) instead of the hub's general form: one form for asking for the iPhone app and for questions, problems and ideas, laid out like Contact & support in the apps, in Aresium's look (dark, or light once the website is switched) and in words that address no one. "Get the iPhone app" on aresium.de, the demo, patrikbreeck.com and the hub's demo open it on Get the app. Patrik's emails now name the app and the topic ("[Aresium] Get the app: …"), and the privacy policy covers the new form.
- **2026-10-31 · arestemis** — Arestemis is on Patrik's iPhone, and its notifications arrive by push, so its Telegram copy is switched off. After his first look its sentences no longer mention the AI (the search fields are “filled in automatically”), and the hunt's start button says “Suche starten”; both reached the phone with build 2.
- **2026-10-30 · aresium** — Aresium after its fourth round: a payment is renamed where its name stands (a tap on the name or its pen) and its category is changed from the chip, Settings' switches read clearly in dark mode, and turning on Face ID or messages no longer flashes the cover. One shop under changing names is now one shop (Vinted's old and new company, dm's spellings, Apple's four names) for grouping, renaming and "also the others", and payments of one name can be added up into one row in a category's list: by a swipe, for a whole category, or everywhere.
- **2026-10-30 · empire** — The four other iPhone apps got the comfort items Patrik chose before TestFlight. Arestemis: a dismissed listing comes back with Undo, the Hunt tab's latest listings take a long press to save or dismiss, Search keeps unsaved changes and offers Save at the top, and Listings loads older listings as you scroll. Aresus: the run report has a close button, a province's page opens its app or website, and the Aresync tab has Settings. Arestoteles asks before throwing away typed text, keeps the tab bar on notes, has a + for a new position and Undo after Done. The Empire app's approvals can be refreshed, and Create account keeps what was typed. The push key is in place, so notifications now reach iPhones. Arestemis went to the phone through TestFlight.
- **2026-10-30 · aresium** — Aresium after its third round: payments can be renamed to names one remembers (Aresium keeps the bank's name for sorting, so new imports get the name too), and all payments of one name are added up on a page of their own, reached by a swipe to the left, a long press or a line on the payment's page. The graph is a setting now and stays on; the header lost its sun and graph buttons. Aresium's messages come from the app itself instead of Telegram: a reminder to import new statements and a review of last month, both made on the iPhone and off until turned on. Build 4 went to the phone through TestFlight.
- **2026-10-30 · aresium** — Aresium after its second round on Patrik's iPhone: scrolling the category list stays smooth while ticking (the work moved off the screen's thread: a pause of 86 ms after a few ticks is now 0.1 ms), a swipe to the right goes back on every screen of the dashboard, and a long press on a payment changes its category. Smaller comforts: Later on questions that can wait, Back in the check of an unknown bank's file, Done on the number keyboard, a question before typed text is thrown away, a spinner while a button works, bigger tap areas, Privacy and Imprint inside the app, and Log out asks first in every Ares app. Build 3 went to the phone through TestFlight.
- **2026-10-30 · aresium** — Aresium learned from its first day on Patrik's iPhone: nothing counts twice any more (a PayPal purchase moved with its shop, money moved from PayPal to the bank, the same payment from two file formats), it sorts far more by itself (on Patrik's real files the payments left unsorted went from 400 to 280; card payments and Vinted now sort, and one correction covers a shop), ticking categories is instant, each own category gets an icon of its own, and an open app follows the iPhone switching between light and dark.
- **2026-10-29 · aresium** — Aresium is on Patrik's iPhone: Apple approved the developer account, all five apps are signed with its team, and the first build went through TestFlight to the phone. It is for Patrik only so far, so Apple did not need to review it. Later builds reach the phone the same way, uploaded with one command from the MacBook.
- **2026-10-28 · aresium** — Aresium reads receipts: a photo or a scan of a receipt is read on the iPhone into shop, date, total and card or cash, and every field can be corrected. A card receipt joins its bank payment so nothing counts twice, and Aresium asks when the amounts differ; a cash receipt comes out of the withdrawal it was paid from. Cash that never came from the bank, such as a gift, can be entered by hand, and a Cash page shows every cash movement in one place. The photo is never kept.
- **2026-10-27 · aresium** — Aresium now opens without an account: a friend installs it and starts with Import data or a tour over made-up data that points at each real button. An optional lock with Face ID or a code of its own protects it. For an unknown bank the app shows the first payments and asks whether they look right, and with two taps the bank's file format (never a payment) or the name of a missing bank reaches Patrik, so Aresium can learn it for everyone. A guide shows how to get the file from 16 banks and PayPal. The privacy policy now has its Aresium section.
- **2026-10-27 · empire** — The hub got a public demo at www.ares-empire.de/demo: a made-up guest with Aresium, Arestemis and Arestoteles on the ring and a made-up chronicle, for anyone without an account; Aresium opens its own demo, the others the request form. The real provinces, plans and chronicle stay behind the login, and the privacy policy now names aresium.de and every demo page.
- **2026-10-27 · aresium** — Aresium got a public demo at aresium.de/demo: the whole website with a made-up account, for anyone and without an account. Nothing reaches the server and nothing is saved; trying to import or change something asks the visitor to log in, and the login page links the demo. Patrik's own aresium.de stays behind the login.
- **2026-10-27 · aresium** — Aresium can now be used by other people with their money staying on their own iPhone: the app reads exports from 25 German banks, sorts payments with 2,815 known shops and learns from each correction (on Patrik's own payments 98% right on day one, about three corrections a month after that), with no AI and nothing sent to a server. Patrik's own Aresium works as before.
- **2026-10-26 · empire** — Every Ares app on an iPhone now lets go of an account the moment it logs out in any of them: widgets drop its numbers, and notifications stop for all apps, not only the one used to log out. The app switcher shows each app's name instead of its screens. These were the last two checks before anyone but Patrik gets an app.
- **2026-10-26 · empire** — The Empire's ring now shows every app an account has access to, and its "+" lists the other apps open to users: asking for one sends the request to Patrik, and the person is told when it is approved and it joins their ring, with an Install button when the app is not on the phone yet. Patrik keeps getting sign-ups and requests by email.
- **2026-10-25 · empire** — The Empire app was reviewed by three independent reviewers before its first TestFlight build, and their fixes are in: the apps that hold only Patrik's data (Aresium, Arestoteles, Aresus) now let in only him, so approving a request can no longer open them; the hub's answers and errors follow one checked shape; tapping a province always opens something; and every website links the privacy policy and imprint.
- **2026-10-25 · empire** — The empire's data is backed up every night: the server makes an encrypted copy of everything that cannot be rebuilt (accounts, Aresium, Arestemis, Aresus, push, the hub's data and the secrets) and keeps a week of them; the MacBook fetches each copy with Aresync, checks it file by file and keeps up to six months. A restore test brought back every transaction.
- **2026-10-25 · empire** — Every Empire app got light mode: Settings → Appearance (like the iPhone, light or dark) in each app, with every colour shared as a light and a dark value, so each future app has both from its first screen. Aresium keeps its red mode on top of either; the Empire app becomes a marble hall by day (ivory wall, antique gold, the bust as a faint relief); the widgets follow the home screen.
- **2026-10-25 · empire** — Every app now creates and runs the one Ares account itself: sign up, reset a password, ask for access to an app, change the password, leave an app (its data goes with it) or delete the account, which removes its data in every service; the privacy policy and imprint went live with a contact form.
- **2026-10-25 · empire** — Every Empire app got a Settings screen behind a gear: language (chosen in the app), notifications, a contact form that reaches Patrik by email, privacy policy, imprint, font licences, version and the account; and each app's name now ends its main screen, seen only when scrolling down.
- **2026-10-25 · arestoteles** — Arestoteles became quick to look things up in: search by meaning on the server (a German question finds the English passage that answers it, with a small open model on the empire's own server), a search field in every tab, short position cards, and notes, edits and "discuss later" marks instead of changing positions on the phone.
- **2026-10-24 · arestoteles** — Arestoteles became the iPhone app for Patrik's Weltbild: his positions first, each with the evidence behind it, topics with briefings, mechanisms, an events timeline and search in English and German; positions can be confirmed, reworded or changed (old views kept with their date), notes edited, and any topic handed to Claude for a discussion that writes back to the vault. The trading bot is gone; the website stays.
- **2026-10-24 · empire** — Every Empire app now speaks English and German: each app follows the iPhone's language, and the servers write their status lines, notes and notifications in that language too. The rule holds for every future app.
- **2026-10-24 · arestemis** — Arestemis's search got simpler: flat or WG, how many move in, sizes, cold and warm rent ranges, dates, portals and extras, each field optional on its own; a sentence can fill in the fields.
- **2026-10-24 · aresus** — Aresus reached the home and lock screens: a widget that says "All running" or names the issue, always with how old the check is; and the Empire app's province cards now carry Aresus's live line for each province.
- **2026-10-24 · aresus** — Aresus went live as the empire's watchtower: every minute it checks each province on the server (services, websites, certificates, deploys), keeps incidents and uptime, and receives a report from every Aresync run on the MacBook and the server. Its iPhone app lists the provinces (issues first, then active, then inactive) and the sync runs, and pushes when something breaks or a sync fails. The server now deploys the hub, Arestemis and Aresus by itself after a push.
- **2026-10-24 · arestemis** — Arestemis became an iPhone app: the search set in fields (places anywhere in Germany), the hunt started and paused from the phone, an AI check of every listing against the whole search, matches with their states, and the application text (written once or by AI per listing). The server was rebuilt for Empire accounts; push notifications replace Telegram once the phone can receive them.
- **2026-10-24 · empire** — One push service for every Empire app: apps register with their Empire login, provinces send through it. Runs as a dry run until Apple approves the developer account.
- **2026-10-24 · empire** — The Empire got its own iPhone app: the approved phone hub rebuilt natively (ring, chronicle, province pages, adding a province, approvals), on the one login shared with Aresium; opening a province starts its app when installed. Runs on the simulator; TestFlight waits for Apple.
- **2026-10-24 · empire** — The hub reached the phone: each account now sees its own ring (Patrik everything plus Approvals; others their provinces and a "+" to add the ones opened to them, today Aresium as coming soon), on the desktop's own wheel and chronicle. Approvals run with Patrik's own login, no superuser secret on the hub.
- **2026-10-23 · aresium** — The Aresium iPhone app grew to the full mobile site: transaction detail and recategorise, import (button and share sheet), the red Aresium mode with the ARESIUM band and intro, and two home-screen widgets (this month's spending line; Groceries + Drogerie). The server now also sends the recategorise choices and each month's running total; the old browser calculation and the paint animation are gone.
- **2026-10-23 · aresium** — The first iPhone app took shape: native SwiftUI Aresium (Empire login, the start, category and month screens of the mobile site) runs on the simulator. To serve website and app alike, Aresium now calculates every dashboard number on the server (`/api/data` v2), checked identical to the old browser calculation on all real data.
- **2026-10-23 · empire** — The hub and Aresium switched from shared passwords to Empire accounts: log in with email + password, sign up and wait for approval, reset a forgotten password.
- **2026-10-23 · empire** — Empire accounts went live at https://auth.ares-empire.de (PocketBase): sign-up, approval by Patrik, per-service access; email via Resend from ares-empire.de.
- **2026-10-23 · empire** — Charted the next campaign: Empire accounts (one login for every service) and native iPhone apps via TestFlight, starting with Aresium. Opened the `empire-ios` repo and the Connections table.
- **2026-06-19 · aresis** — Aresis joined the empire: a personal exposure scanner + privacy-remediation engine (OSINT → LLM severity judge → remediation → report), with the full pipeline running end to end. Cloned local and registered as a province.
- **2026-06-15 · empire** — Reworked the hub into a clean, modern black-and-gold room: the marble bust at the left edge, the provinces on a stretched circle, the chronicle as a timeline beneath, and an EXPAND view for the empire's expansions.
- **2026-06-15 · empire** — Went live at https://www.ares-empire.de — TLS, gated by the empire access key, behind the shared nginx.
- **2026-06-15 · empire** — Aresium and Arestoteles took their place as the first two provinces of the empire.

---

## Notes for later

- **Login:** Empire accounts since 2026-10-23 — `webauth/server.py` (run by `ares-empire.service`
  behind Caddy) logs people in against PocketBase; sign-up needs Patrik's approval. The old single
  access key is gone.
- **Front door:** since 2026-10-21 **Caddy** on the host (`/etc/caddy/Caddyfile`) serves every
  domain with automatic HTTPS; it replaced the `insureai_nginx` container (`deploy/nginx/` is history).
- **Accounts:** `empire-accounts.service` (PocketBase) at https://auth.ares-empire.de — see
  [docs/ACCOUNTS.md](docs/ACCOUNTS.md).
- **SSO:** the hub becomes the shared identity provider so entering a province from the
  hub doesn't ask you to log in again. Routes are left room for this; not built yet.
