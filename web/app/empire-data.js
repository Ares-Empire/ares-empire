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
      { at: "2026-10-31", project: "aresium", text: "Aresium after its fifth round on Patrik's iPhone: a payment's day reads as a date (\"4.\"), a name's months open as pages of their own, Settings no longer stalls, and the add-up icon always means all or none in its list. The graph is read by holding a finger on it and sliding, a tap opens that month, and it moves away while the categories scroll (a switch in Settings); the header's buttons lost their boxes. The tour now walks through all of it in 18 steps. Builds 6 and 7 went to the phone through TestFlight." },
      { at: "2026-10-31", project: "aresium", text: "Aresium got its own contact page at aresium.de/contact (German: /kontakt) instead of the hub's general form: one form for asking for the iPhone app and for questions, problems and ideas, laid out like Contact & support in the apps, in Aresium's look (dark, or light once the website is switched) and in words that address no one. \"Get the iPhone app\" on aresium.de, the demo, patrikbreeck.com and the hub's demo open it on Get the app. Patrik's emails now name the app and the topic (\"[Aresium] Get the app: …\"), and the privacy policy covers the new form." },
      { at: "2026-10-31", project: "arestemis", text: "Arestemis is on Patrik's iPhone, and its notifications arrive by push, so its Telegram copy is switched off. After his first look its sentences no longer mention the AI (the search fields are “filled in automatically”), and the hunt's start button says “Suche starten”; both reached the phone with build 2." },
      { at: "2026-10-30", project: "aresium", text: "Aresium after its fourth round: a payment is renamed where its name stands (a tap on the name or its pen) and its category is changed from the chip, Settings' switches read clearly in dark mode, and turning on Face ID or messages no longer flashes the cover. One shop under changing names is now one shop (Vinted's old and new company, dm's spellings, Apple's four names) for grouping, renaming and \"also the others\", and payments of one name can be added up into one row in a category's list: by a swipe, for a whole category, or everywhere." },
      { at: "2026-10-30", project: "empire", text: "The four other iPhone apps got the comfort items Patrik chose before TestFlight. Arestemis: a dismissed listing comes back with Undo, the Hunt tab's latest listings take a long press to save or dismiss, Search keeps unsaved changes and offers Save at the top, and Listings loads older listings as you scroll. Aresus: the run report has a close button, a province's page opens its app or website, and the Aresync tab has Settings. Arestoteles asks before throwing away typed text, keeps the tab bar on notes, has a + for a new position and Undo after Done. The Empire app's approvals can be refreshed, and Create account keeps what was typed. The push key is in place, so notifications now reach iPhones. Arestemis went to the phone through TestFlight." },
      { at: "2026-10-30", project: "aresium", text: "Aresium after its third round: payments can be renamed to names one remembers (Aresium keeps the bank's name for sorting, so new imports get the name too), and all payments of one name are added up on a page of their own, reached by a swipe to the left, a long press or a line on the payment's page. The graph is a setting now and stays on; the header lost its sun and graph buttons. Aresium's messages come from the app itself instead of Telegram: a reminder to import new statements and a review of last month, both made on the iPhone and off until turned on. Build 4 went to the phone through TestFlight." },
      { at: "2026-10-30", project: "aresium", text: "Aresium after its second round on Patrik's iPhone: scrolling the category list stays smooth while ticking (the work moved off the screen's thread: a pause of 86 ms after a few ticks is now 0.1 ms), a swipe to the right goes back on every screen of the dashboard, and a long press on a payment changes its category. Smaller comforts: Later on questions that can wait, Back in the check of an unknown bank's file, Done on the number keyboard, a question before typed text is thrown away, a spinner while a button works, bigger tap areas, Privacy and Imprint inside the app, and Log out asks first in every Ares app. Build 3 went to the phone through TestFlight." },
      { at: "2026-10-30", project: "aresium", text: "Aresium learned from its first day on Patrik's iPhone: nothing counts twice any more (a PayPal purchase moved with its shop, money moved from PayPal to the bank, the same payment from two file formats), it sorts far more by itself (on Patrik's real files the payments left unsorted went from 400 to 280; card payments and Vinted now sort, and one correction covers a shop), ticking categories is instant, each own category gets an icon of its own, and an open app follows the iPhone switching between light and dark." },
      { at: "2026-10-29", project: "aresium", text: "Aresium is on Patrik's iPhone: Apple approved the developer account, all five apps are signed with its team, and the first build went through TestFlight to the phone. It is for Patrik only so far, so Apple did not need to review it. Later builds reach the phone the same way, uploaded with one command from the MacBook." },
      { at: "2026-10-28", project: "aresium", text: "Aresium reads receipts: a photo or a scan of a receipt is read on the iPhone into shop, date, total and card or cash, and every field can be corrected. A card receipt joins its bank payment so nothing counts twice, and Aresium asks when the amounts differ; a cash receipt comes out of the withdrawal it was paid from. Cash that never came from the bank, such as a gift, can be entered by hand, and a Cash page shows every cash movement in one place. The photo is never kept." },
      { at: "2026-10-27", project: "aresium", text: "Aresium now opens without an account: a friend installs it and starts with Import data or a tour over made-up data that points at each real button. An optional lock with Face ID or a code of its own protects it. For an unknown bank the app shows the first payments and asks whether they look right, and with two taps the bank's file format (never a payment) or the name of a missing bank reaches Patrik, so Aresium can learn it for everyone. A guide shows how to get the file from 16 banks and PayPal. The privacy policy now has its Aresium section." },
      { at: "2026-10-27", project: "empire", text: "The hub got a public demo at www.ares-empire.de/demo: a made-up guest with Aresium, Arestemis and Arestoteles on the ring and a made-up chronicle, for anyone without an account; Aresium opens its own demo, the others the request form. The real provinces, plans and chronicle stay behind the login, and the privacy policy now names aresium.de and every demo page." },
      { at: "2026-10-27", project: "aresium", text: "Aresium got a public demo at aresium.de/demo: the whole website with a made-up account, for anyone and without an account. Nothing reaches the server and nothing is saved; trying to import or change something asks the visitor to log in, and the login page links the demo. Patrik's own aresium.de stays behind the login." },
      { at: "2026-10-27", project: "aresium", text: "Aresium can now be used by other people with their money staying on their own iPhone: the app reads exports from 25 German banks, sorts payments with 2,815 known shops and learns from each correction (on Patrik's own payments 98% right on day one, about three corrections a month after that), with no AI and nothing sent to a server. Patrik's own Aresium works as before." },
      { at: "2026-10-26", project: "empire", text: "Every Ares app on an iPhone now lets go of an account the moment it logs out in any of them: widgets drop its numbers, and notifications stop for all apps, not only the one used to log out. The app switcher shows each app's name instead of its screens. These were the last two checks before anyone but Patrik gets an app." },
      { at: "2026-10-26", project: "empire", text: "The Empire's ring now shows every app an account has access to, and its \"+\" lists the other apps open to users: asking for one sends the request to Patrik, and the person is told when it is approved and it joins their ring, with an Install button when the app is not on the phone yet. Patrik keeps getting sign-ups and requests by email." },
      { at: "2026-10-25", project: "empire", text: "The Empire app was reviewed by three independent reviewers before its first TestFlight build, and their fixes are in: the apps that hold only Patrik's data (Aresium, Arestoteles, Aresus) now let in only him, so approving a request can no longer open them; the hub's answers and errors follow one checked shape; tapping a province always opens something; and every website links the privacy policy and imprint." },
      { at: "2026-10-25", project: "empire", text: "The empire's data is backed up every night: the server makes an encrypted copy of everything that cannot be rebuilt (accounts, Aresium, Arestemis, Aresus, push, the hub's data and the secrets) and keeps a week of them; the MacBook fetches each copy with Aresync, checks it file by file and keeps up to six months. A restore test brought back every transaction." },
      { at: "2026-10-25", project: "empire", text: "Every Empire app got light mode: Settings → Appearance (like the iPhone, light or dark) in each app, with every colour shared as a light and a dark value, so each future app has both from its first screen. Aresium keeps its red mode on top of either; the Empire app becomes a marble hall by day (ivory wall, antique gold, the bust as a faint relief); the widgets follow the home screen." },
      { at: "2026-10-25", project: "empire", text: "Every app now creates and runs the one Ares account itself: sign up, reset a password, ask for access to an app, change the password, leave an app (its data goes with it) or delete the account, which removes its data in every service; the privacy policy and imprint went live with a contact form." },
      { at: "2026-10-25", project: "empire", text: "Every Empire app got a Settings screen behind a gear: language (chosen in the app), notifications, a contact form that reaches Patrik by email, privacy policy, imprint, font licences, version and the account; and each app's name now ends its main screen, seen only when scrolling down." },
      { at: "2026-10-25", project: "arestoteles", text: "Arestoteles became quick to look things up in: search by meaning on the server (a German question finds the English passage that answers it, with a small open model on the empire's own server), a search field in every tab, short position cards, and notes, edits and \"discuss later\" marks instead of changing positions on the phone." },
      { at: "2026-10-24", project: "arestoteles", text: "Arestoteles became the iPhone app for Patrik's Weltbild: his positions first, each with the evidence behind it, topics with briefings, mechanisms, an events timeline and search in English and German; positions can be confirmed, reworded or changed (old views kept with their date), notes edited, and any topic handed to Claude for a discussion that writes back to the vault. The trading bot is gone; the website stays." },
      { at: "2026-10-24", project: "empire", text: "Every Empire app now speaks English and German: each app follows the iPhone's language, and the servers write their status lines, notes and notifications in that language too. The rule holds for every future app." },
      { at: "2026-10-24", project: "arestemis", text: "Arestemis's search got simpler: flat or WG, how many move in, sizes, cold and warm rent ranges, dates, portals and extras, each field optional on its own; a sentence can fill in the fields." },
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
