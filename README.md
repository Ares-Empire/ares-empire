# Ares Empire

The central hub / home of the empire — a single overview that ties together every
"Ares" service and (later) provides shared sign-on (SSO) across them.

> **On the name.** "Ares" is Patrik's long-standing online handle — not a tribute to the
> war god, just a name that's grown on him. The Greek-war-god association is treated as
> *aesthetic* (marble, command, gravitas), never devotional.

## Naming decision — **"Ares Empire"** (not just "Ares")

Chosen over the bare "Ares" because:

- It names a **collection**, which is exactly what the hub is — Aresium + Arestoteles +
  future services. "Ares" alone reads as one app; "Ares Empire" reads as the thing that
  *contains* the apps.
- It carries the grand, sovereign feel the project is going for, and matches how the
  integration docs already refer to it ("Ares Empire", "the empire home").
- It disambiguates from the individual products, all of which start with "Ares…".

Short forms: directory `ares-empire`, future domain candidate `ares-empire.*` /
`aresempire.*` (TBD), display name **Ares Empire**.

## What lives here (to be built)

- **Service overview** — a card grid of the empire's services with live status and
  deep-links: **Aresium** (personal finance · aresium.de), **Arestoteles** (AI portfolio ·
  arestoteles.de), and room for the next ones.
- **Central hub / SSO provider** — the adopted empire home and future single sign-on
  (today each app ships its own custom login; the hub becomes the shared identity later —
  see arestoteles `docs/09`).

## Design language

Shared "Ares Empire" look from Aresium + Arestoteles: near-black wall, glassmorphism,
Space Grotesk + JetBrains Mono, restrained motion. The hub is **clean / modern / professional**
— **polished gold used sparingly as an accent** (not glare) over black, lit by faint Mars-red +
steel-blue ambient, with a monochrome marble bust embedded at the left edge. Each *product* gets
its own marble bust of a fitting figure (Arestoteles → Aristotle); the **empire** keeps the
**Ares bust** as its mark (the intro's slamming figure + the favicon).

## Logo

**Direction chosen: an Ares marble bust in gilded war-gear** — the empire's sovereign mark,
consistent with the bust-per-product language but elevated (helmeted, martial, **gold-armored**)
so it reads as the *crown* above the philosopher busts rather than a peer to them. White marble
face/head + **polished shiny gold helmet & armor** against pure black: a regal marble-gold-black
palette that's unmistakably the empire's, while the sub-products stay pure white marble.

The actual artwork is **deferred to Claude Design** (same path the Aristotle bust took).
The copy-paste brief — including the resolved style choices (white-marble face, gilded
Corinthian helmet pushed back, bearded, gold cuirass, black ground) — is in
[`brand/LOGO_PROMPT.md`](brand/LOGO_PROMPT.md). Drop the generated PNG in `brand/` as `ares-bust.png`.

### The Arestoteles hub button, until the logo lands

The button in the Arestoteles header now reads **"Ares Empire"** (plain wordmark) with the
old red status-dot and "›" chevron removed. Once `ares-bust.png` exists, swap the wordmark
for **the mark + "Ares Empire"** (mark-only is too ambiguous before the brand is known).

---

## The hub website (`web/`) — built & **live at https://www.ares-empire.de**

The hub is built, in the empire's house style — **no build step** (React-from-CDN + Babel-in-browser
+ vanilla `window`-global modules, exactly like Aresium / Arestoteles). The Ares bust now lives
background-removed at `brand/ares-bust.png` (+ `web/brand/`).

**Run locally**

```bash
python3 -m http.server 8099 --directory web    # → http://localhost:8099
```

**What's there**

- **Slam intro** (`web/app/empire-intro.js`) — the bust drops; fine gold fissures burst from the
  root all at once and grow outward; "ARES EMPIRE" slams in in polished gold (single shine), then it morphs into the hub.
- **The figure** — a monochrome marble bust (`brand/head1.png`) embedded flush at the left edge
  (screen-blend + edge mask), gazing toward the circle (`web/app/app.jsx`).
- **Orbital circle** (`web/app/ring.jsx`) — the provinces ride a stretched, offset ellipse as
  horizontal tabs (mark · GOLD NAME · status). Drag / scroll / ← → to revolve; click the focused one to spread into the **project board**.
- **Boards** (`web/app/panels.jsx`) — a count-adaptive card grid (2 → L/R, 3 → L/M/R, 4 → quadrants …)
  with context, reused for the project board and the **EXPANSIONS** view (the plans, via **EXPAND**).
- **Timeline** — the chronicle as a clean horizontal ribbon below the circle.
- **CONQUER forge** — name a province → it generates the seed `CLAUDE.md`, the manifest entry and
  the Claude Code handoff (copy buttons), then adds it to the circle.
- **Login / logout** — Empire accounts (email + password, sign-up with approval, password reset) via
  `webauth/server.py` + the `web/login.html` template; a logout control sits top-right. See [docs/ACCOUNTS.md](docs/ACCOUNTS.md).
- **Privacy policy and imprint** — `/datenschutz`, `/privacy`, `/impressum`, `/imprint`, open without login
  (`webauth/legal.py`, text in `web/legal/`, self-hosted font in `web/fonts/`). A page still holding `[ADDRESS]` or
  `[lead to confirm]` answers 404; `LEGAL_PREVIEW=1` shows drafts locally. What the text is based on:
  [docs/PRIVACY.md](docs/PRIVACY.md). Linked ("Privacy · Imprint") from the login page and, signed in, from the
  hub's bottom-right corner (phone: the end of the page), via `window.LegalLinks` in `web/app/panels.jsx`.
- **Contact pages** — the Ares Empire's `/contact` and `/kontakt` (also its general contact) and Arestemis's
  `/arestemis/contact` and `/arestemis/kontakt`, open without login, each one form for asking for the iPhone app
  (`?topic=access`) and for questions, problems and ideas, in the app's own look, light or dark (`webauth/contact.py`,
  the looks in `web/contact/`). They share the sending and the layout with aresium.de/contact byte for byte
  (`web/shared/forms/`, README there), are served only while the privacy policy in their language is, and post from the
  browser straight to the account server's open `contact` collection, which mails Patrik
  ([docs/ACCOUNTS.md](docs/ACCOUNTS.md) → Website contact form).

**Source of truth** — [`EMPIRE.md`](EMPIRE.md) (narrative) + `web/app/empire-data.js`
(`window.EMPIRE`, the manifest the circle renders from). Add a province by appending to both; the circle
grows on its own.

**Deploy** (live on this server, behind Caddy — `/etc/caddy/Caddyfile`)

- `ares-empire.service` (`deploy/systemd/`) runs `webauth/server.py` on the docker bridge
  `172.18.0.1:5185`, reading settings from `.env`. Logins are checked against `empire-accounts`
  (PocketBase, `deploy/install-accounts.sh`).
- `empire-push.service` (`push/`, `deploy/install-push.sh`): one push service for every Empire app; Caddy routes
  `/api/push/*` to it. Contract and operating notes: [docs/PUSH.md](docs/PUSH.md).
- `empire-backup.timer` (`backup/`, `deploy/install-backup.sh`): the nightly backup of the data that cannot be
  rebuilt; the MacBook fetches it with Aresync. [docs/BACKUP.md](docs/BACKUP.md).
- Caddy proxies the domain → the service and handles TLS itself. (`deploy/nginx/` and the TLS
  scripts are from the old nginx setup, kept for reference.)
- **Updating the site:** edit `web/…`; the service serves from disk live (no rebuild).
