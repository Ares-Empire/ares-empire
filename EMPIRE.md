# ARES EMPIRE — the living charter

The central hub / home of the empire — one throne that ties together every "Ares"
service. This file is the **always-active empire doc**: the canonical, human-readable
source of truth for the vision, the design language, the provinces (projects) and the
expansions (ideas). The chronicle (what was done to conquer what) is in [CHRONICLE.md](CHRONICLE.md): add a line
there after meaningful work, as its header says.

Its machine twin is [`web/app/empire-data.js`](web/app/empire-data.js) (`window.EMPIRE`) —
the manifest the hub website actually renders from. **Keep the two in step.** When a
province is added or its state changes, update *both* this file and the manifest.

> On the name: "Ares" is the owner's long-standing handle. The war-god association is
> treated as *aesthetic* — marble, gold, command, gravitas — never devotional.

## Now (updated 2026-11-22)

Six iPhone apps are on TestFlight, all on the shared standard ([docs/IPHONE-APPS.md](docs/IPHONE-APPS.md) → Every
app has): the Empire app, Aresium, Arestemis, Aresus with Aresync, Arestoteles (all since 2026-11-01) and Arestia, the
owner's flat (since 2026-11-20, no Ares account, its data outside every repo). Aresium is also open to outside testers
through a public TestFlight link; their data stays on their iPhone. Files go from the iPhone to the MacBook through
Aresus's Aresync tab ([docs/ARESYNC-DROP.md](docs/ARESYNC-DROP.md)); receipts filed with their inventory line
(its step 2) are next. The big steps of 2026-10-25 (light mode,
TestFlight, Aresium for other people, Aresync file sharing) are done. **Next:** new apps, each built on the standard
from its first screen. Open items: the board, `empire-ios` → open phone checks, [PRIVACY.md](docs/PRIVACY.md) → To do.

**Decisions in force:**
- Other people's Aresium data stays on their iPhone: imports, categories, storage; no bank data on the server; its
  section in the privacy policy before anyone else gets it (owner, 2026-10-25). Plan and progress:
  [docs/ARESIUM-FOR-OTHERS.md](docs/ARESIUM-FOR-OTHERS.md).
- Aresus and Aresync stay the owner's own tools and never go to others (owner, 2026-10-25).
- Builds for the owner go through internal TestFlight (no Apple review). An app that goes to other people (external
  testers or the App Store) is reviewed by Apple, and its demo account gets an extra address on the owner's domain.
  Aresium's outside testers get the TestFlight link directly: no account, no hub step.

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
**A good structure is worth more work now** (owner, 2026-10-23; in full in the global CLAUDE.md, "Apps: good
structure is worth more work now"): when the quick way (a workaround, copying logic into a second place) would make
later changes slower or cause bugs, choose the better structure, even if it takes longer now. Judgment, not a rule to
merge things; separate pieces are fine when they are simpler. Restructure in steps that keep the live service working; before switching, show the new version gives the same results,
then delete the old code; when it is much bigger than the task, tell the owner what, why and how big first. Example:
Aresium's website calculated its numbers in the browser; an iPhone app would have had to copy them, so they moved to
the server first ([IPHONE-APPS.md](docs/IPHONE-APPS.md), step 3).

**Every app speaks English and German** (owner, 2026-10-24), the current ones and every future one: the iPhone's
language decides, English is the fallback. Interface text is translated, including the sentences servers write for the
apps and the notifications; content people wrote is not. Rules: [docs/LANGUAGES.md](docs/LANGUAGES.md).

**Data that cannot be rebuilt is backed up every night** (owner, 2026-10-25): a service that starts storing such
data adds it to the nightly backup in the same change ([docs/BACKUP.md](docs/BACKUP.md) → New data).

**A website's light or dark travels with its links** (owner, 2026-11-01 and 2026-11-07): a link to another Empire
site that reads it passes `?look=light` or `?look=dark`, and that page opens in it for the visit without remembering
it. patrikbreeck.com passes its look; the hub, which is always dark, passes `dark` (`web/app/empire-api.js` →
`passLook`, the legal pages' contact links); the Arestemis demo passes the look it shows to its request form. Pages
that read it: aresium.de, arestemis.de and the hub's contact pages. A new site with light and dark reads it too.

**Councils check the big choices** (owner, 2026-11-05): a few agents, each with its own role and question, look at a
plan or a piece of work blind, then check each other's answers, and Claude brings the owner one verdict. Used for choices
that are hard to undo, milestones, a bug that comes back, and an expansion before it gets a plan. Method and roles:
[docs/COUNCIL.md](docs/COUNCIL.md). When the owner says "council", this is what he means.

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
| **Arestoteles** | CONQUERED | arestoteles.de | The owner's Weltbild on the phone — positions, topics, mechanisms, events; read, search, edit, discuss with Claude. |
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
| **Aresium** | **Empire login** (website, hub hand-off and API for the app) | **on the owner's iPhone** (internal TestFlight, 2026-10-29) | `aresium` |
| **Arestemis** | **Empire login** (API for the app; its demo at arestemis.de) | **on the owner's iPhone** (internal TestFlight, 2026-10-31): [docs/ARESTEMIS-APP.md](docs/ARESTEMIS-APP.md) | `Arestemis` |
| **Aresus** (+ Aresync) | **Empire login** (API for the app, no website; Aresync reports with machine tokens) | **on the owner's iPhone** (internal TestFlight, 2026-10-31): [docs/ARESUS-APP.md](docs/ARESUS-APP.md) | `aresus`, `aresync` |
| **Arestoteles** | **Empire login** (API for the app); the website keeps its own login | **on TestFlight** (internal, 2026-11-01): [docs/ARESTOTELES-APP.md](docs/ARESTOTELES-APP.md) | `Arestoteles`, vault `carlsenares/opinions` |
| **Ares Empire** (hub) | **Empire login** — sign-up, approval and password reset live here; the push service for all apps ([docs/PUSH.md](docs/PUSH.md)) | **on TestFlight** (internal, 2026-11-01): [docs/EMPIRE-APP.md](docs/EMPIRE-APP.md) | `ares-empire` |

All empire repos live in the GitHub organization **[Ares-Empire](https://github.com/Ares-Empire)**
(aresync follows once every laptop runs the org-aware version). Each repo keeps its own
visibility. **Public since 2026-11-02:** `aresium`, `empire-ios`, `ares-empire`, `Arestoteles`, `ares` and `AresOS`, as fresh
repos with cleaned history (the old ones are private archives, `<name>-archive-2026-11`). Private: `Arestemis` (its
sites research and server briefs stay there), `aresus`, `aresync`, `arescope` and `companions` (until it is shown).
Public repos hold no personal data ([PRIVACY.md](docs/PRIVACY.md) → Owner file) and never say how
Arestemis gets past a site's blocks. **Licence (owner, 2026-11-08):** every Empire repo is free for non-commercial use
under the PolyForm Noncommercial License 1.0.0 (`LICENSE.md`, holder "Ares Empire"; companions too); `ares`
(patrikbreeck.com) has none, so its look and texts stay all rights reserved. The organization's GitHub front page is
the public repo `.github` (`profile/README.md`).

iPhone apps for every province live in one repo, **`empire-ios`** (name deliberately not
`ares…`, so the empire sync doesn't list it as a province of its own).

---

## Expansions (future plans)

Mirror of `EMPIRE.ideas` — the **EXPAND** view. Open one from the board and it pre-fills the CONQUER forge.

- **Empire accounts** (live since 2026-10-23) — one account for every service and app: sign up with email + password, the owner approves, every province trusts the login. Plan: [docs/ACCOUNTS.md](docs/ACCOUNTS.md).
- **iPhone apps** (live: six on TestFlight) — real native apps installed via TestFlight, starting with Aresium, then widgets. Plan: [docs/IPHONE-APPS.md](docs/IPHONE-APPS.md).
- **Aresgora** — a public agora: the empire's outward-facing landing for the usable services.
- **The Council** (live since 2026-11-06 as the board and Aresus's For you tab) — open work and the owner's decisions in one place, so nothing waits unnoticed once a session moves on. A scan of every repo finds work that was built but never merged or shipped; sessions name themselves by topic, and open work goes to its topic's session, not to the owner. Only what needs his own decision or action reaches him, in Aresus's "Waiting on you" tab: one tap answers, or opens the session that asked. Planned by two councils (2026-11-03, 2026-11-05: [record](docs/reviews/2026-11-05-work-board.md)); building since 2026-11-06.

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
   `CLAUDE.md`, appends the province to the manifest + a line to the Chronicle (`CHRONICLE.md`), and
   `git init`s. The new province takes its place in the circle.
4. (Optional, later) a local `POST /api/conquer` companion does step 3 on one button.

**There is always an active empire doc:** this file + the manifest. Claude Code reads them
to know the empire's shape, and appends to the **Chronicle** (`CHRONICLE.md`) whenever it conquers.

---


## Notes for later

- **Server:** Caddy on the host serves every domain with HTTPS (`/etc/caddy/Caddyfile`, since 2026-10-21). The hub's
  `webauth/server.py` (`ares-empire.service`) logs people in against PocketBase (`empire-accounts.service`,
  auth.ares-empire.de, [docs/ACCOUNTS.md](docs/ACCOUNTS.md)); sign-up needs the owner's approval.
- **Not built yet:** single sign-on, so entering a province from the hub doesn't ask for the login again (routes leave
  room for it).
