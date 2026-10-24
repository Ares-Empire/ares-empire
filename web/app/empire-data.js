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
        logo: "brand/hermes.webp",
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
        logo: "brand/arestoteles.webp",
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
        logo: "brand/artemis.webp",
        status: "CONQUERED",
        domain: "",
        blurb: "Apartment sniper — claims new flat listings the moment they post.",
        detail: {
          about: "The huntress. Arestemis watches the Munich housing portals and pounces on a " +
            "new listing the instant it appears — first to the viewing, first to apply. Runs " +
            "24/7 as a Telegram bot in the empire (formerly the FlatSniper project).",
          features: ["Real-time listing watch", "Instant alerts", "Fast-track applying"],
          setup: "", wip: [], ideas: [], changelog: [],
        },
      },
      {
        slug: "arescribe",
        name: "Arescribe",
        url: "",
        logo: "brand/athena.webp",
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
        logo: "brand/aeolus.webp",
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
        logo: "brand/cerberus.webp",
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
        logo: "brand/janus.webp",
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
        logo: "brand/zeus.webp",
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
      {
        slug: "aresis",
        name: "Aresis",
        url: "",
        logo: "brand/nemesis.png",
        status: "BESIEGING",
        domain: "",
        blurb: "Privacy guardian — scans your exposed personal data and proposes fixes.",
        detail: {
          about: "Nemesis, who balances exposure. Aresis is a personal exposure scanner and " +
            "privacy-remediation engine: feed it identifiers you own (email, username, name), it " +
            "runs them through OSINT sources, has an LLM judge each finding by severity, and " +
            "proposes concrete fixes — to shrink your digital footprint, never to investigate others. " +
            "The full scan→judge→remediate→report pipeline runs end to end.",
          features: [
            "OSINT exposure scan across breach & footprint sources",
            "LLM severity judgement (info → critical)",
            "Concrete remediation steps per finding",
            "Self-audit only (ownership-gated)",
          ],
          setup: "", wip: ["Deploy behind shared nginx"], ideas: ["Optional auth → privacy SaaS"], changelog: [],
        },
      },
    ],

    // ── Expansions: future plans (the EXPAND view). Open one → it pre-fills the Forge. ──
    ideas: [
      { title: "Empire accounts", note: "One account for every service and app: sign up with email + password, Patrik approves, every province trusts the login." },
      { title: "iPhone apps", note: "Real native apps via TestFlight, starting with Aresium — then widgets. Code in the empire-ios repo." },
      { title: "Aresgora", note: "A public agora: the empire's outward-facing landing for the services people can actually use." },
      { title: "The Watchtower", note: "A single status board — uptime, last deploy and health for every conquered service." },
    ],

    // ── Chronicle: what was done, newest first (Claude Code appends here) ──
    chronicle: [
      { at: "2026-10-24", project: "aresus", text: "Aresus reached the home and lock screens: a widget that says \"All running\" or names the issue, always with how old the check is; and the Empire app's province cards now carry Aresus's live line for each province." },
      { at: "2026-10-24", project: "aresus", text: "Aresus went live as the empire's watchtower: every minute it checks each province on the server (services, websites, certificates, deploys), keeps incidents and uptime, and receives a report from every Aresync run on the MacBook and the server. Its iPhone app lists the provinces (issues first, then active, then inactive) and the sync runs, and pushes when something breaks or a sync fails. The server now deploys the hub, Arestemis and Aresus by itself after a push." },
      { at: "2026-10-24", project: "arestemis", text: "Arestemis became an iPhone app: the search set in fields (places anywhere in Germany), the hunt started and paused from the phone, an AI check of every listing against the whole search, matches with their states, and the application text (written once or by AI per listing). The server was rebuilt for Empire accounts; push notifications replace Telegram once the phone can receive them." },
      { at: "2026-10-24", project: "empire", text: "One push service for every Empire app: apps register with their Empire login, provinces send through it. Runs as a dry run until Apple approves the developer account." },
      { at: "2026-10-24", project: "empire", text: "The Empire got its own iPhone app: the approved phone hub rebuilt natively (ring, chronicle, province pages, adding a province, approvals), on the one login shared with Aresium; opening a province starts its app when installed. Runs on the simulator; TestFlight waits for Apple." },
      { at: "2026-10-24", project: "empire", text: "The hub reached the phone: each account now sees its own ring (Patrik everything plus Approvals; others their provinces and a \"+\" to add the ones opened to them, today Aresium as coming soon), on the desktop's own wheel and chronicle. Approvals run with Patrik's own login, no superuser secret on the hub." },
      { at: "2026-10-23", project: "aresium", text: "The Aresium iPhone app grew to the full mobile site: transaction detail and recategorise, import (button and share sheet), the red Aresium mode with the ARESIUM band and intro, and two home-screen widgets (this month's spending line; Groceries + Drogerie). The server now also sends the recategorise choices and each month's running total; the old browser calculation and the paint animation are gone." },
      { at: "2026-10-23", project: "aresium", text: "The first iPhone app took shape: native SwiftUI Aresium (Empire login, the start, category and month screens of the mobile site) runs on the simulator. To serve website and app alike, Aresium now calculates every dashboard number on the server (`/api/data` v2), checked identical to the old browser calculation on all real data." },
      { at: "2026-10-23", project: "empire", text: "The hub and Aresium switched from shared passwords to Empire accounts: log in with email + password, sign up and wait for approval, reset a forgotten password." },
      { at: "2026-10-23", project: "empire", text: "Empire accounts went live at https://auth.ares-empire.de (PocketBase): sign-up, approval by Patrik, per-service access; email via Resend from ares-empire.de." },
      { at: "2026-10-23", project: "empire", text: "Charted the next campaign: Empire accounts (one login for every service) and native iPhone apps via TestFlight, starting with Aresium. Opened the `empire-ios` repo and the Connections table." },
      { at: "2026-06-19", project: "aresis", text: "Aresis joined the empire: a personal exposure scanner + privacy-remediation engine (OSINT → LLM severity judge → remediation → report), the full pipeline running end to end. Registered as a province." },
      { at: "2026-06-16", project: "aresync", text: "Aresync took the field: a git-based sync that mirrors every GitHub repo across the MacBook, the Windows Lenovo and the server — auto commit → rebase → push, clone-if-new. The macOS agent runs live (login + daily); the Windows task is built and awaiting setup." },
      { at: "2026-06-15", project: "empire", text: "Reworked the hub into a clean, modern black-and-gold room: the marble bust at the left edge, the provinces on a stretched circle, the chronicle as a timeline beneath, and an EXPAND view for the empire's expansions." },
      { at: "2026-06-15", project: "empire", text: "Went live at www.ares-empire.de — TLS, gated by the empire access key, behind the shared nginx." },
      { at: "2026-06-15", project: "empire", text: "Aresium and Arestoteles took their place as the first two provinces of the empire." },
    ],

    STATUS,
  };

  window.EMPIRE = EMPIRE;
})();
