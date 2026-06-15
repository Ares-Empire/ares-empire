/* Ares Empire — the manifest the hub renders from (window.EMPIRE).

   This is the machine-readable source of truth for the website: the orbital ring,
   the War Council (ideas) and the Chronicle (changelog) all read from here. It is the
   web-facing twin of the root EMPIRE.md — Claude Code keeps the two in step, and the
   CONQUER flow appends to `projects` / `chronicle` here when a new project is forged.

   Edit this file (or have Claude Code edit it) to add a service — the ring grows on
   its own, no UI code change. Keep it plain data; no imports, no build step. */
(function () {
  "use strict";

  // status vocabulary — the empire's martial states (drives the gold status word on each tab)
  const STATUS = {
    SCOUTED:    { label: "SCOUTED",    tone: "scout" },   // an idea, not yet built
    BESIEGING:  { label: "BESIEGING",  tone: "wip"   },   // under active conquest (WIP)
    CONQUERED:  { label: "CONQUERED",  tone: "live"  },   // live and held
    FORTIFYING: { label: "FORTIFYING", tone: "hold"  },   // live, under maintenance
  };

  const EMPIRE = {
    name: "ARES EMPIRE",
    tagline: "The hub of the empire — every Ares service, one throne.",

    // ── the services in orbit (the ring). order = orbital order ──────────────
    projects: [
      {
        slug: "aresium",
        name: "Aresium",
        url: "https://aresium.de",
        logo: "brand/aresium.svg",
        status: "CONQUERED",
        domain: "aresium.de",
        blurb: "Personal finance command — VR Bank + PayPal, imported and understood.",
      },
      {
        slug: "arestoteles",
        name: "Arestoteles",
        url: "https://arestoteles.de",
        logo: "brand/arestoteles.png",
        status: "CONQUERED",
        domain: "arestoteles.de",
        blurb: "AI portfolio strategist — theses, falsifiers, conviction.",
      },
    ],

    // ── War Council: future expansions (openable). Promote one → it pre-fills CONQUER. ──
    ideas: [
      { title: "Empire SSO", note: "One sign-in across every service — enter the hub, walk into any province already logged in." },
      { title: "Aresgora", note: "A public agora: the empire's outward-facing landing for the services people can actually use." },
      { title: "The Watchtower", note: "A single status board — uptime, last deploy and health for every conquered service." },
    ],

    // ── Chronicle: what was done to conquer what (Claude Code appends here) ──
    chronicle: [
      { at: "2026-06-15", project: "empire", text: "Went live at www.ares-empire.de — TLS, gated by the empire access key, behind the shared nginx. Aresium took its crimson rising-line mark." },
      { at: "2026-06-15", project: "empire", text: "Raised the hub: molten-gold slam intro, the orbital project ring, the Oracle, stars mode and the CONQUER forge." },
      { at: "2026-06-15", project: "empire", text: "Adopted the marble-gold-black crown language from Aresium + Arestoteles; the Ares bust takes the throne." },
    ],

    // ── the Oracle's voice: lines Ares speaks when consulted ──
    oracle: [
      "Speak, and the empire listens.",
      "Every province was once a wilderness. Name the next.",
      "Hold what you have taken before you reach for more.",
      "A plan survives no contact with the enemy — yet march with one anyway.",
      "The throne is not the work. The work is the conquest.",
      "Two provinces stand. The map has room for legions more.",
      "Fortify before you feast. A held line is worth two won.",
      "What you cannot measure, you do not yet hold.",
      "Begin. The first stone of every wall looks like nothing.",
      "Strategy is patience wearing armor.",
    ],

    STATUS,
  };

  // backdrop choice — the eclipse the ring orbits (swap to any brand/moonN.png)
  EMPIRE.sky = { moon: "brand/moon4.png" };

  window.EMPIRE = EMPIRE;
})();
