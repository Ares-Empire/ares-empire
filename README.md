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

Shared "Ares Empire" look already used by Aresium + Arestoteles: black wall, marble,
glassmorphism, Space Grotesk + JetBrains Mono, restrained motion. Each *product* gets its
own marble bust of a fitting figure (Arestoteles → Aristotle). The **empire itself** gets
the **Ares bust** as its crown mark (see below).

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
