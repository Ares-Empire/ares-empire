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
      { at: "2026-11-02", project: "aresium", text: "Aresium now says what a month costs on average and how much of it is fixed: under the overview's total, the average of the finished months and the fixed part, which opens the fixed costs (rent, subscriptions, insurance), each found by its amount, how often it comes and a steady day, with when the next one is due; a cancelled subscription moves to Ended, and one counted by mistake is taken out with a long press. The income side shows regular money in the same way. Aresium also went to Apple's beta review for testers outside the empire, and a walk through a fresh install fixed three snags for newcomers first: skipping the category list left everything unsorted, the first days of a month showed almost nothing, and a German button read like 'delete'. Build 19 went to the phone through TestFlight." },
      { at: "2026-11-02", project: "arestemis", text: "Arestemis explains itself now: a tour of eight steps, shown once after the first login and again from Settings, walks through sample searches in the app's own language, from starting a search to what a Preismonitor and a page watch are for. Patrik asked for it when \"Webseite beobachten\" read as too vague; the tour's frame is shared with Aresium's, whose tour looks exactly as before. App build 13." },
      { at: "2026-11-02", project: "aresync", text: "Aresync carries files from the iPhone to the MacBook from anywhere: in Aresus's Aresync tab a photo, a camera picture or any file is sent with a folder in Documents or Downloads chosen on the phone (a new one can be made there, or Sort later) and a name. The server encrypts it on arrival with a key whose secret half only the MacBook holds; the Mac's own program fetches it within a minute while the Mac is awake, puts it in place without overwriting anything, and a quiet push says it was delivered. The first file from the phone landed on 2026-11-02 (Aresus builds 2 and 3); sent files are deleted from the list with a swipe as in Mail. Aresus in the iPhone's share sheet comes next." },
      { at: "2026-11-02", project: "arestemis", text: "Arestemis has a fourth kind of search, the Preismonitor: one product in one shop, its price kept as a curve over 30, 90 or 365 days, a push when it falls under a chosen price or is back in stock, or both, switchable at any time on the monitor's page. It reads the shop's own product data first and asks the AI only where a page has none. New search became a page of four cards with examples, and every search can be renamed in place without starting it again. App builds 11 and 12." },
      { at: "2026-11-02", project: "aresium", text: "Aresium links money paid back for several payments at once: select the expenses someone paid back, tick the payments that came in from them, and the money is shared out expense by expense, the oldest first, each paid back in full before the next, until it runs out; or the other way round, several transfers paying back one expense. Before linking, a summary shows what each expense gets back and what stays open or still counts as income, and one undo takes every link back. A payment that came in can never pay back more than it brought. Build 18 went to the phone through TestFlight." },
      { at: "2026-11-02", project: "aresium", text: "Bank files reach Aresium from anywhere now: shared from Files, Safari or AirDrop it opens and imports them, and a file dragged from Files onto its main screen is imported the same way, held until the lock opens. Watching the share sheet end to end for the first time found two bugs, both fixed: iOS's copy of a shared bank file was never deleted after reading, and an MT940 statement shared while Aresium was closed was refused. Build 17 went to the phone through TestFlight." },
      { at: "2026-11-02", project: "aresium", text: "Aresium can take money paid back off what was spent: when someone pays back an expense, all of it or a share, the two payments are linked by hand on either payment's page (suggestions first: the same amount, half, a third, within days; a search for paybacks in parts), and only one's own share counts as spent, in the expense's month and category, while the payback no longer counts as income. Nothing is matched without asking, and every other payment still counts as it happened. Patrik asked after Aresium's overview looked far too high. Build 16 went to the phone through TestFlight." },
      { at: "2026-11-02", project: "arestemis", text: "Arestemis can watch a web page now: give it an address and say in your own words what to look for (\"when KALLAX costs under 45 €\", \"when the Mensa has Schnitzel\"), and it reads the page every 15 minutes to once a day and tells you when it happens. Only a change goes to the AI, a list that merely reorders is no change, and a page that refuses the server is shown as stopped rather than knocked on again; pages of the sites it hunts and anything inside the server's own network are refused. It was tried on 17 real pages first. eBay went live the same afternoon with its own keys, and the app's Angebote tab now shows what is new grouped by search, and each search's listings on their own, with a search over all found listings, best match first. App builds 9 and 10." },
      { at: "2026-11-02", project: "aresium", text: "Selecting payments in Aresium works like Mail now: a finger sliding down the circles ticks every payment it passes and unticks them again on the way back, and held near the top or bottom the list scrolls on by itself. Selecting also became calm: a recording showed the bounce Patrik felt (each tick slid its circle in from the side and the count rolled letter by letter), so a tick now simply appears. Build 15 went to the phone through TestFlight." },
      { at: "2026-11-02", project: "aresium", text: "Aresium can go through what is not sorted name by name: after an import it offers to show the unsorted payments grouped by who they are with, the most payments first, and one tap on a category sorts all of a name's payments at once and teaches Aresium the name for the next import. Money in and money out of the same person are separate cards, skip and undo are always there, and nothing already sorted is touched. Not sorted's list starts with the same offer. Build 14 went to the phone through TestFlight." },
      { at: "2026-11-02", project: "arestemis", text: "Arestemis hunts on five sites for things now: besides Kleinanzeigen and MTB-News Bikemarkt it reads mydealz's deals, IKEA Preowned (used IKEA furniture near the search's towns, which OpenStreetMap now gives coordinates) and Vinted. Each was tested with a real hunt: Kallax shelves near Garching with the accessories filtered out, Levi's 501 on Vinted with brand, size and the buyer-protection fee. The app greys a site that cannot serve the chosen delivery (IKEA only for pickup, Vinted and mydealz only shipped). App build 8." },
      { at: "2026-11-02", project: "arestemis", text: "Arestemis became a hunter for more than flats: an account can run several hunts, and a new kind of hunt looks for things for sale on Kleinanzeigen (search words, words to leave out, a price with an allowance for negotiable prices, condition, pickup near a place or shipping, private sellers). The AI check filters out spare parts and accessories and warns of signs of a scam; a new hunt checks what is online once, quietly. Things are read every 3 minutes and each site has an hourly budget, so the flat hunt keeps its pace. Underneath, the server was split into a shared hunting core and one search type per kind, proven to find exactly the same flats before and after. App build 6." },
      { at: "2026-11-01", project: "aresium", text: "Aresium knows Germany's local places: a list of 264,744 shops, restaurants, cafés, practices and other places from OpenStreetMap sorts a payment at a place it knows into its kind, packed so it costs the iPhone about 13 MB (as plain data it took 103 MB, measured and refused first). With a third round of sorting fixes, a new person with Patrik's files now finds 984 of 1,246 payments sorted on day one and needs 103 corrections over 14 months instead of 111. The list can be downloaded at aresium.de/osm under the ODbL. Build 13 went to the phone through TestFlight." },
      { at: "2026-11-01", project: "empire", text: "The Ares Empire and Arestemis got contact pages like Aresium's: www.ares-empire.de/contact (German /kontakt) replaces the hub's old form and stays the Empire's general contact, and www.ares-empire.de/arestemis/contact is Arestemis's own. Each is one form for asking for the iPhone app and for questions, problems and ideas, in the app's own look, light or dark, in words that address no one, and both share one form with Aresium's. patrikbreeck.com and the hub's demo now ask for each app on its own page." },
      { at: "2026-11-01", project: "aresium", text: "Aresium can now change many payments at once: a circle in a category's list ticks payments as in Mail, and Kategorie or Name moves, adds to or renames all of them with one question for their shops and an undo. Saving an added category now asks whether to leave the old one and whether the shop's other payments should get it too. Build 12 went to the phone through TestFlight, with the first round of sorting and reading fixes." },
      { at: "2026-11-01", project: "aresium", text: "Aresium now measures how well it reads bank files and sorts payments, with test sets of 228 hard bank files and 2,039 invented payments whose right answers two independent AI judges set without seeing each other. The first round of fixes found against them: sorting leaves far less unsorted (missed 304 to 135, wrong 21 to 4, and as well on the held-back part nobody looked at), and no test file is read wrong any more (40 silent errors to 0). A category name that exists is now used instead of refused (Freunde for income too), and categories can be renamed and deleted, their payments sorted again. Build 11 went to the phone through TestFlight." },
      { at: "2026-11-01", project: "aresium", text: "Aresium can search: a magnifying glass finds a name, your own or the bank's, best match first, and opens all its payments. A tap on a day of the graph opens that day's spending and income, side by side to swipe. A shop now shows one name even when its bank line changed over the year (Vinted, Apple), and unsorted money in reads Nicht sortiert. Build 10 went to the phone through TestFlight." },
      { at: "2026-11-01", project: "arestoteles", text: "Arestoteles on the phone, its first evening: a note now closes the moment it is saved and goes to the vault's Inbox in the background, also when the app is left right away; a note that cannot be sent waits on the phone and the tabs say so. The vault is unpacked and indexed away from the screen's work, so the app no longer stalls when the vault loads or after an edit. Build 2 went to the phone through TestFlight." },
      { at: "2026-11-01", project: "empire", text: "The Empire app was uploaded to TestFlight for Patrik's iPhone, so all five Empire apps now reach his phone. A check of everything that differs between the simulator and a real iPhone found nothing in the way." },
      { at: "2026-11-01", project: "arestoteles", text: "Arestoteles was uploaded to TestFlight for Patrik's iPhone. Its Aristotle lost the watermark an image tool had printed across the face: the app icon, the app, arestoteles.de and the hub's ring now show the hub's clean bust. When the app drops its saved notes after a logout in another Ares app, they now leave iPhone search too, and its copy of the vault stays out of the iPhone's backups, since it can always be downloaded again." },
      { at: "2026-11-01", project: "aresium", text: "Aresium lets every category have a side: one's own categories now work for money in too, and a spending category that also gets money back (Freunde, when a friend pays back) can be offered for money in from the change window, without cluttering the menus. Every payment now counts once, as it happened: money out as Ausgaben, money in as Einnahmen, each under its own category. Build 9 went to the phone through TestFlight." },
      { at: "2026-11-01", project: "arestemis", text: "Arestemis now searches ImmoScout24, Germany's biggest flat portal, in every town, and Immowelt in every town it knows instead of only München. Kleinanzeigen changed its list pages on the evening of 31 October; Arestemis missed its new listings for part of the evening until the fix went live. In Settings, Bewerbung became three rows like the others: a switch for automatic texts, a page with one's own text or with notes every automatic text includes, and About you; the automatic text is now written from the facts about the person and those notes. Build 3 went to the phone through TestFlight." },
      { at: "2026-10-31", project: "aresium", text: "Aresium makes a new category where one is chosen: the window that changes a payment's category, the receipt window and Bargeld eintragen offer \"Neue Kategorie\". The name is typed once, the category gets its own icon and colour and is already picked, so a payment no longer needs a detour through Settings. Build 8 went to the phone through TestFlight." },
      { at: "2026-10-31", project: "aresus", text: "Aresus, with its Aresync tab, was uploaded to TestFlight for Patrik's iPhone. It now also watches each of Arestemis's search portals and tells only Patrik when one is blocked or failing: only after an hour without a break, as a normal notification that does not break through Focus, and silently if it comes back within six hours; the \"running again\" note replaces the alert. Short blocks no longer send anything, and a crash during such a problem still alerts at once. The false alarm about Aresium's retired Telegram bot is gone." },
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
