/* Ares Empire — the manifest the hub renders from (window.EMPIRE).

   This is the machine-readable source of truth for the website: the orbital circle
   (projects), the EXPANSIONS board (ideas) and the timeline (chronicle) all read from
   here. It is the web-facing twin of the root EMPIRE.md — Claude Code keeps the two in
   step, and the CONQUER flow appends to `projects` / `chronicle` here when one is forged.

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

    // ── Expansions: future plans (the EXPAND view). Open one → it pre-fills the Forge. ──
    ideas: [
      { title: "Empire SSO", note: "One sign-in across every service — enter the hub, walk into any province already logged in." },
      { title: "Aresgora", note: "A public agora: the empire's outward-facing landing for the services people can actually use." },
      { title: "The Watchtower", note: "A single status board — uptime, last deploy and health for every conquered service." },
    ],

    // ── Chronicle: what was done, newest first (Claude Code appends here) ──
    chronicle: [
      { at: "2026-06-15", project: "empire", text: "Reworked the hub into a clean, modern black-and-gold room: the marble bust at the left edge, the provinces on a stretched circle, the chronicle as a timeline beneath, and an EXPAND view for the empire's expansions." },
      { at: "2026-06-15", project: "empire", text: "Went live at www.ares-empire.de — TLS, gated by the empire access key, behind the shared nginx." },
      { at: "2026-06-15", project: "empire", text: "Aresium and Arestoteles took their place as the first two provinces of the empire." },
    ],

    STATUS,
  };

  window.EMPIRE = EMPIRE;
})();
