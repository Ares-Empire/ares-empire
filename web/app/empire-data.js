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
    SCOUTED:    { label: "SCOUTED",    tone: "scout"  },  // an idea, not yet built
    MUSTERING:  { label: "MUSTERING",  tone: "muster" },  // declared & gearing up — not started yet
    BESIEGING:  { label: "BESIEGING",  tone: "wip"    },  // under active conquest (WIP)
    CONQUERED:  { label: "CONQUERED",  tone: "live"   },  // live and held
    FORTIFYING: { label: "FORTIFYING", tone: "hold"   },  // live, under maintenance
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
        logo: "brand/hermes.png",
        status: "CONQUERED",
        domain: "aresium.de",
        blurb: "Personal finance command — VR Bank + PayPal, imported and understood.",
        // detail: the full-screen province page. Any field may be omitted — the page shows a
        // tidy empty state for what isn't filled in yet. `changelog` falls back to the chronicle
        // entries tagged with this slug.
        detail: {
          about: "The empire's personal-finance command. Aresium imports VR Bank and PayPal " +
            "activity, reconciles it, and turns raw statements into an understood picture of " +
            "balances, cash flow and where the money actually goes.",
          features: [
            "VR Bank + PayPal import",
            "Transaction categorisation & reconciliation",
            "Balance and cash-flow overview",
          ],
          setup: "",
          wip: [],
          ideas: [],
          changelog: [],
        },
      },
      {
        slug: "arestoteles",
        name: "Arestoteles",
        url: "https://arestoteles.de",
        logo: "brand/arestoteles.png",
        status: "CONQUERED",
        domain: "arestoteles.de",
        blurb: "AI portfolio strategist — theses, falsifiers, conviction.",
        detail: {
          about: "An AI portfolio strategist. Arestoteles forms theses, names the falsifiers " +
            "that would break them, and tracks conviction — so positions are held or cut for " +
            "stated reasons rather than noise.",
          features: [
            "Thesis + falsifier tracking",
            "Conviction scoring",
            "Telegram control",
          ],
          setup: "",
          wip: [],
          ideas: [],
          changelog: [],
        },
      },

      // ── MUSTERING: declared provinces, gearing up — not built yet ──────────────
      {
        slug: "arestemis",
        name: "Arestemis",
        url: "",
        logo: "brand/artemis.png",
        status: "MUSTERING",
        domain: "",
        blurb: "Apartment sniper — claims new flat listings the moment they post.",
        detail: {
          about: "The huntress. Arestemis (the Flatsniper bot) watches the housing portals and " +
            "pounces on a new listing the instant it appears — first to the viewing, first to apply. " +
            "Already running as flatsniper; linking it into the empire is the next step.",
          features: ["Real-time listing watch", "Instant alerts", "Fast-track applying"],
          setup: "", wip: [], ideas: [], changelog: [],
        },
      },
      {
        slug: "arescribe",
        name: "Arescribe",
        url: "",
        logo: "brand/athena.png",
        status: "MUSTERING",
        domain: "",
        blurb: "Maps-review scribe — text it a place and notes, it writes the review.",
        detail: {
          about: "Athena's craft. Text the Arescribe bot a place plus a few notes and it composes " +
            "a fitting Google Maps review automatically — and can post it for you.",
          features: ["Telegram bot input", "Place-aware review generation", "Google Maps posting"],
          setup: "", wip: [], ideas: [], changelog: [],
        },
      },
      {
        slug: "aresolus",
        name: "Aresolus",
        url: "",
        logo: "brand/aeolus.png",
        status: "MUSTERING",
        domain: "",
        blurb: "Flight finder — hunts the best flights; trains and more to come.",
        detail: {
          about: "Keeper of the winds. Aresolus searches for the best flights for a trip and " +
            "surfaces the strongest options; rail and other modes are planned.",
          features: ["Best-fare flight search", "Flexible date / route hunting"],
          ideas: ["Trains & buses", "Price-drop alerts"],
          setup: "", wip: [], changelog: [],
        },
      },
      {
        slug: "arescrypt",
        name: "Arescrypt",
        url: "",
        logo: "brand/cerberus.png",
        status: "MUSTERING",
        domain: "",
        blurb: "Personal password vault — the empire's three-headed guard.",
        detail: {
          about: "Cerberus at the gate. Arescrypt is a personal password manager — a single, " +
            "guarded vault for every credential.",
          features: ["Encrypted vault", "Personal credential store"],
          setup: "", wip: [], ideas: [], changelog: [],
        },
      },
      {
        slug: "aresync",
        name: "Aresync",
        url: "",
        logo: "brand/janus.png",
        status: "BESIEGING",
        domain: "",
        blurb: "Git sync across Windows & Mac — every repo, everywhere, automatically.",
        detail: {
          about: "The two-faced god of thresholds. Aresync keeps every " +
            "project in step across the Windows Lenovo at home, the MacBook on the go and the " +
            "server — it mirrors all GitHub repos locally, auto-commits and pushes local work, " +
            "and pulls everything else. The macOS half runs live; the Windows half is built and " +
            "awaiting setup.",
          features: [
            "Mirrors every GitHub repo locally",
            "Auto commit → rebase → push",
            "macOS LaunchAgent (login + daily)",
            "Windows Task Scheduler",
          ],
          setup: "",
          wip: ["Windows machine setup", "IntelliJ / Artemis uni-project sync"],
          ideas: [],
          changelog: [],
        },
      },
      {
        slug: "aresus",
        name: "Aresus",
        url: "",
        logo: "brand/zeus.png",
        status: "MUSTERING",
        domain: "",
        blurb: "The watchtower — monitors every province, alerts when one falls.",
        detail: {
          about: "Zeus on the throne, watching all. Aresus is the empire's watchtower: it monitors " +
            "every project, alerts the moment something goes down, and gathers status in one place.",
          features: ["Uptime & health monitoring", "Down alerts", "Single status board"],
          setup: "", wip: [], ideas: [], changelog: [],
        },
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
      { at: "2026-06-16", project: "aresync", text: "Aresync took the field: a git-based sync that mirrors every GitHub repo across the MacBook, the Windows Lenovo and the server — auto commit → rebase → push, clone-if-new. The macOS agent runs live (login + daily); the Windows task is built and awaiting setup." },
      { at: "2026-06-15", project: "empire", text: "Reworked the hub into a clean, modern black-and-gold room: the marble bust at the left edge, the provinces on a stretched circle, the chronicle as a timeline beneath, and an EXPAND view for the empire's expansions." },
      { at: "2026-06-15", project: "empire", text: "Went live at www.ares-empire.de — TLS, gated by the empire access key, behind the shared nginx." },
      { at: "2026-06-15", project: "empire", text: "Aresium and Arestoteles took their place as the first two provinces of the empire." },
    ],

    STATUS,
  };

  window.EMPIRE = EMPIRE;
})();
