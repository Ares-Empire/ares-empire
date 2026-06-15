# ARES EMPIRE — the living charter

The central hub / home of the empire — one throne that ties together every "Ares"
service. This file is the **always-active empire doc**: the canonical, human-readable
source of truth for the vision, the design language, the provinces (projects), the war
council (ideas) and the chronicle (what was done to conquer what).

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
| **Palette** | White marble · **polished gold** · pure black. Sub-products are silver-on-black; the **empire is gold-on-black**. |
| **Type** | Space Grotesk (text) · JetBrains Mono (numbers/code) · **Cinzel** (imperial small-caps: status words, kickers). |
| **Surfaces** | Black wall, glassmorphism (blurred translucent cards with a bright top edge), tight negative letter-spacing, restrained motion. |
| **Crown mark** | The **Ares marble bust in gilded war-gear** (`brand/ares-bust.png`) — the sovereign mark above the philosopher busts. |
| **Backdrop** | A gold "diamond-ring" **eclipse** (`brand/moon4.png`) the project ring literally **orbits**; corona glow + parallax + slow breathe. |
| **Signature motion** | The **molten-gold slam**: the bust drops, cracks the wall, and the fissures run radiant molten gold; "ARES EMPIRE" slams in in gold. |

The gold wordmark is the silver `.ares-word` text-clip gradient retuned to gold, with a
slow metallic glint sweeping across it.

---

## The hub (what the website is)

A single full-screen scene:

- **Intro (first visit / per session):** molten-gold slam, then it **morphs** straight
  into the hub (the intro doesn't scroll away — it dissolves into the throne room).
- **Top-left:** the Ares bust — also the **Oracle**, consult it for a line (and a
  suggested next conquest drawn from the War Council).
- **Top-center:** **ARES EMPIRE** in gold (the crown title).
- **Center:** the **orbital ring** — every province as a tab (logo + gold name + status),
  spinnable in 3D; the front one faces you. One tab is **CONQUER** (the empty throne).
- **Bottom:** the big gold **ARES EMPIRE** wordmark band, like the product pages.
- **Stars mode:** the ring scatters into a constellation over the eclipse.
- **War Council** (ideas) and **The Chronicle** (this changelog) open as side scrolls.

---

## Provinces (the project registry)

Mirror of `EMPIRE.projects`. Status vocabulary: `SCOUTED` (idea) → `BESIEGING` (WIP) →
`CONQUERED` (live & held) → `FORTIFYING` (live, maintenance).

| Province | State | Domain | What it is |
|---|---|---|---|
| **Aresium** | CONQUERED | aresium.de | Personal finance command — VR Bank + PayPal, imported and understood. |
| **Arestoteles** | CONQUERED | arestoteles.de | AI portfolio strategist — theses, falsifiers, conviction. |

---

## War Council (future expansions)

Mirror of `EMPIRE.ideas`. Promote one from the hub and it pre-fills the CONQUER forge.

- **Empire SSO** — one sign-in across every service; enter the hub, walk into any province already logged in.
- **Aresgora** — a public agora: the empire's outward-facing landing for the usable services.
- **The Watchtower** — one status board: uptime, last deploy and health per conquered service.

---

## The conquest loop (how a province is born)

The hub is the **display + intent**; Claude Code (or a tiny local companion) is the **hands**
— a browser can't create directories or `git init` on your machine, so the forge hands off.

1. On the hub, open **CONQUER** (the throne expands in place). Set the **name** + a one-line blurb.
2. The forge produces three things with copy buttons:
   - the new province's seed **`CLAUDE.md`**,
   - its **manifest entry** for `web/app/empire-data.js`,
   - a **handoff command** to paste into Claude Code.
3. Run the handoff in Claude Code → it scaffolds `projects/<slug>/`, drops the seed
   `CLAUDE.md`, appends the province to the manifest + a line to this Chronicle, and
   `git init`s. The throne reveal fires; the new province takes its place in the ring.
4. (Optional, later) a local `POST /api/conquer` companion does step 3 on one button.

**There is always an active empire doc:** this file + the manifest. Claude Code reads them
to know the empire's shape, and appends to the **Chronicle** below whenever it conquers.

---

## The Chronicle (what was done to conquer what)

Newest first. Mirror of `EMPIRE.chronicle`; Claude Code appends here as it works
("did X to conquer Y").

- **2026-06-15 · empire** — Went live at https://www.ares-empire.de — TLS, gated by the empire access key, behind the shared nginx. Aresium took its crimson rising-line mark (`web/brand/aresium.svg`).
- **2026-06-15 · empire** — Raised the hub: molten-gold slam intro, the orbital project ring, the Oracle, stars mode and the CONQUER forge.
- **2026-06-15 · empire** — Adopted the marble-gold-black crown language from Aresium + Arestoteles; the Ares bust takes the throne.

---

## Notes for later

- **Login:** live — the empire sign-in (`web/login.html`) is gated by `webauth/server.py`
  (scrypt + HMAC-signed cookie), run by `ares-empire.service` and reverse-proxied by the shared
  `insureai_nginx` at https://www.ares-empire.de. Secrets live in `.env` (never committed; on a
  fresh box regenerate with `webauth/gen_password.py`).
- **SSO:** the hub becomes the shared identity provider so entering a province from the
  hub doesn't ask you to log in again. Routes are left room for this; not built yet.
