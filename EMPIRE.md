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

## Expansions (future plans)

Mirror of `EMPIRE.ideas` — the **EXPAND** view. Open one from the board and it pre-fills the CONQUER forge.

- **Empire SSO** — one sign-in across every service; enter the hub, walk into any province already logged in.
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

- **2026-06-19 · aresis** — Aresis joined the empire: a personal exposure scanner + privacy-remediation engine (OSINT → LLM severity judge → remediation → report), with the full pipeline running end to end. Cloned local and registered as a province.
- **2026-06-15 · empire** — Reworked the hub into a clean, modern black-and-gold room: the marble bust at the left edge, the provinces on a stretched circle, the chronicle as a timeline beneath, and an EXPAND view for the empire's expansions.
- **2026-06-15 · empire** — Went live at https://www.ares-empire.de — TLS, gated by the empire access key, behind the shared nginx.
- **2026-06-15 · empire** — Aresium and Arestoteles took their place as the first two provinces of the empire.

---

## Notes for later

- **Login:** live — the empire sign-in (`web/login.html`) is gated by `webauth/server.py`
  (scrypt + HMAC-signed cookie), run by `ares-empire.service` and reverse-proxied by the shared
  `insureai_nginx` at https://www.ares-empire.de. Secrets live in `.env` (never committed; on a
  fresh box regenerate with `webauth/gen_password.py`).
- **SSO:** the hub becomes the shared identity provider so entering a province from the
  hub doesn't ask you to log in again. Routes are left room for this; not built yet.
