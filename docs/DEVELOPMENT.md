# Developing the Ares Empire hub

How the hub website, the login and the server parts work, and how they are deployed. The overview is in the
[README](../README.md); the projects' map and rules are in [EMPIRE.md](../EMPIRE.md).

## The hub website (`web/`)

The hub is in the empire's house style, with **no build step** (React-from-CDN + Babel-in-browser
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
  `webauth/server.py` + the `web/login.html` template; a logout control sits top-right. See [docs/ACCOUNTS.md](ACCOUNTS.md).
- **Privacy policy and imprint** — `/datenschutz`, `/privacy`, `/impressum`, `/imprint`, open without login
  (`webauth/legal.py`, text in `web/legal/`, self-hosted font in `web/fonts/`). A page still holding `[ADDRESS]` or
  `[lead to confirm]` answers 404; `LEGAL_PREVIEW=1` shows drafts locally. What the text is based on:
  [docs/PRIVACY.md](PRIVACY.md). Linked ("Privacy · Imprint") from the login page and, signed in, from the
  hub's bottom-right corner (phone: the end of the page), via `window.LegalLinks` in `web/app/panels.jsx`.
- **Contact pages** — the Ares Empire's `/contact` and `/kontakt` (also its general contact) and Arestemis's
  `/arestemis/contact` and `/arestemis/kontakt`, open without login, each one form for asking for the iPhone app
  (`?topic=access`) and for questions, problems and ideas, in the app's own look, light or dark (`webauth/contact.py`,
  the looks in `web/contact/`). They share the sending and the layout with aresium.de/contact byte for byte
  (`web/shared/forms/`, README there), are served only while the privacy policy in their language is, and post from the
  browser straight to the account server's open `contact` collection, which mails Patrik
  ([docs/ACCOUNTS.md](ACCOUNTS.md) → Website contact form).

**Source of truth** — [`EMPIRE.md`](../EMPIRE.md) (narrative) + `web/app/empire-data.js`
(`window.EMPIRE`, the manifest the circle renders from). Add a province by appending to both; the circle
grows on its own.

**Deploy** (live on this server, behind Caddy — `/etc/caddy/Caddyfile`)

- `ares-empire.service` (`deploy/systemd/`) runs `webauth/server.py` on the docker bridge
  `172.18.0.1:5185`, reading settings from `.env`. Logins are checked against `empire-accounts`
  (PocketBase, `deploy/install-accounts.sh`).
- `empire-push.service` (`push/`, `deploy/install-push.sh`): one push service for every Empire app; Caddy routes
  `/api/push/*` to it. Contract and operating notes: [docs/PUSH.md](PUSH.md).
- `empire-backup.timer` (`backup/`, `deploy/install-backup.sh`): the nightly backup of the data that cannot be
  rebuilt; the MacBook fetches it with Aresync. [docs/BACKUP.md](BACKUP.md).
- Caddy proxies the domain → the service and handles TLS itself. (`deploy/nginx/` and the TLS
  scripts are from the old nginx setup, kept for reference.)
- **Updating the site:** edit `web/…`; the service serves from disk live (no rebuild).
