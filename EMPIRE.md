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

---

## Provinces (the project registry)

Mirror of `EMPIRE.projects`. Status vocabulary: `SCOUTED` (idea) → `BESIEGING` (WIP) →
`CONQUERED` (live & held) → `FORTIFYING` (live, maintenance).

| Province | State | Domain | What it is |
|---|---|---|---|
| **Aresium** | CONQUERED | aresium.de | Personal finance command — VR Bank + PayPal, imported and understood. |
| **Arestoteles** | CONQUERED | arestoteles.de | AI portfolio strategist — theses, falsifiers, conviction. |
| **Aresync** | BESIEGING | — | Git sync across Windows & Mac — every repo, everywhere, automatically. |
| **Aresis** | BESIEGING | — | Privacy guardian — scans your exposed personal data and proposes fixes. Scan→judge→remediate pipeline runs end to end. |

---

## Connections

Which provinces use the **Empire login** ([docs/ACCOUNTS.md](docs/ACCOUNTS.md)) and which have an
**iPhone app** ([docs/IPHONE-APPS.md](docs/IPHONE-APPS.md)). Every project keeps its own repo and
folder; being "part of the empire" is tracked here, not by moving folders (aresync clones every
repo as a top-level folder, and live services and data volumes depend on their paths).

| Province | Login | iPhone app | Repo |
|---|---|---|---|
| **Aresium** | **Empire login** (website, hub hand-off and API for the app) | **built** (simulator; TestFlight pending) | `aresium` |
| **Arestemis** | **Empire login** (API for the app, no website) | **built** (simulator; TestFlight pending): [docs/ARESTEMIS-APP.md](docs/ARESTEMIS-APP.md) | `Arestemis` |
| **Aresus** (+ Aresync) | **Empire login** (API for the app, no website; Aresync reports with machine tokens) | **built** (simulator; TestFlight pending): [docs/ARESUS-APP.md](docs/ARESUS-APP.md) | `aresus`, `aresync` |
| **Arestoteles** | own login | — | `Arestoteles` |
| **Ares Empire** (hub) | **Empire login** — sign-up, approval and password reset live here; the push service for all apps ([docs/PUSH.md](docs/PUSH.md)) | **built** (simulator; TestFlight pending): [docs/EMPIRE-APP.md](docs/EMPIRE-APP.md) | `ares-empire` |

All empire repos live in the GitHub organization **[Ares-Empire](https://github.com/Ares-Empire)**
(aresync follows once every laptop runs the org-aware version). Each repo keeps its own
visibility, so code can go public project by project.

iPhone apps for every province live in one repo, **`empire-ios`** (name deliberately not
`ares…`, so the empire sync doesn't list it as a province of its own).

---

## Expansions (future plans)

Mirror of `EMPIRE.ideas` — the **EXPAND** view. Open one from the board and it pre-fills the CONQUER forge.

- **Empire accounts** — one account for every service and app: sign up with email + password, Patrik approves, every province trusts the login. Plan: [docs/ACCOUNTS.md](docs/ACCOUNTS.md).
- **iPhone apps** — real native apps installed via TestFlight, starting with Aresium, then widgets. Plan: [docs/IPHONE-APPS.md](docs/IPHONE-APPS.md).
- **Aresgora** — a public agora: the empire's outward-facing landing for the usable services.
- **The Watchtower** — one status board: uptime, last deploy and health per conquered service.

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
("did X to conquer Y").

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
