# iPhone apps — decision record

**Decided 2026-10-23.** Status (2026-10-24): **Aresium, the Empire app, Arestemis and Aresus built** in `empire-ios`,
running on the simulator with one shared login; TestFlight and push wait for Apple to approve the developer account.

## The decision

- Empire services become **real native iPhone apps** (SwiftUI), not website wrappers.
  Native is what makes widgets, Face ID and other iPhone features possible later.
- **No single codebase for website and app** (asked 2026-10-23): a wrapped website loses the native
  features above, and React Native would replace SwiftUI while still not sharing screens with the
  React website. What is shared instead: all logic on the server (one API) and one design
  ([EMPIRE.md → How we build apps](../EMPIRE.md#how-we-build-apps-web--ios)).
- Patrik gets the **paid Apple Developer Program** membership (99 USD/year, shown in EUR at
  sign-up). The free Apple ID route was rejected: those apps stop opening after 7 days and
  need a re-install from the Mac every week.
- Apps are installed through **TestFlight**, not the public App Store.
- Every app speaks **English and German** from its first screen, following the iPhone's language
  ([LANGUAGES.md](LANGUAGES.md), 2026-10-24).
- The apps log in with an **Ares Empire account** from day one (see [ACCOUNTS.md](ACCOUNTS.md)),
  even while Patrik is the only user, so sharing later is a server-only change.
- Code lives in one repo for all iPhone apps: **[`empire-ios`](https://github.com/Ares-Empire/empire-ios)**.
  Each app talks to its service's existing API; the services stay where they are.
- iPhone work happens with **Claude Code on the MacBook** (Xcode only runs on macOS), so
  Claude can build, run the simulator and fix errors directly. Server work stays on the server.

## iPhone features: check for every app

When an app is built or extended, check which of these fit it (Patrik, 2026-10-24: "remember to check if an app we
built can benefit from iPhone features"). Note the answer in the app's decision record, also when it is "none".

- Widgets (home and lock screen), interactive widgets and Control Center controls (do something without opening the app)
- Live Activities (a running thing on the lock screen and Dynamic Island: a hunt, an incident, a sync)
- Siri and Shortcuts (App Intents; also Spotlight and the Action button)
- Share sheet in and out (send a file or link into the app), notifications with actions
- Spotlight search of the app's content
- Maps and location, Calendar and Reminders, camera and document scanning, Face ID
- Apple's on-device AI (Foundation Models, iOS 26; iPhone 15 Pro or newer): private classification and summaries
  without data leaving the phone

 (checked 2026-10-23 against Apple's docs)

| Claim | Verified | Source |
|---|---|---|
| Free Apple ID: apps expire after **7 days**, max **3 apps** per device | ✅ | Apple, *Compare memberships* |
| TestFlight: each build is testable for **90 days** | ✅ | App Store Connect Help, *TestFlight overview* |
| TestFlight internal testers: up to **100**, must be App Store Connect users of the account | ✅ | App Store Connect Help, *Add internal testers* |
| Internal TestFlight builds need **no Apple review** | ✅ widely documented; Apple's pages only mention review for external testers | |
| External testers: up to **10,000** via invite/link; the first build needs a light Beta App Review | ✅ | App Store Connect Help, *TestFlight overview* |
| Paid account, installing straight from Xcode: valid for about **1 year** | ✅ (Apple DTS on the developer forums) | |
| Membership price: **99 USD/year**, local currency at sign-up | ✅ | Apple Developer, *Enrollment* |

**Correction to the earlier plan:** *Unlisted App Store distribution* is meant for limited
audiences of an organisation (employees, partners, students, conference attendees). Apple
reviews each request and rejects beta apps. A personal app for one person may well be
declined, so it is **not** the fallback we rely on. TestFlight is the plan; unlisted is only
worth trying once the app is shared with a real group of users.

## Every app has (the standard, 2026-10-24)

- **Settings** behind a gear icon in the header: the app's own settings, language (asks, then the app restarts
  inside itself in the new one), notifications (apps that send them), contact & support (a form that reaches Patrik by
  email), privacy policy, imprint, font licences, version, and the account: change password, log out, leave this app
  (its access and its data), delete the Ares account. Built once in `empire-ios/Shared/`; a new app only adds its own
  section.
- **The one Ares account, run from the app itself** ([ACCOUNTS.md](ACCOUNTS.md) → Accounts in every app, 2026-10-25):
  its login creates an account and resets a password, an account without this app can ask for access, so nobody
  needs the Empire app. A new app whose server keeps data per account adds `DELETE /api/<service>/me` and its
  internal deletion route, so leaving the app and deleting the account reach it.
- **Its name at the end of the main screen**, seen only when scrolling down (`WordmarkBand`, shared).
- **English and German** ([LANGUAGES.md](LANGUAGES.md)).
- **Light and dark** (Patrik, 2026-10-24: "we will add it and its best to do it before making more apps so it can
  become a part of standard design"; built 2026-10-25 for all five apps and both widgets). Settings → Appearance: like
  the iPhone, light, dark. Every colour is a light/dark pair in the shared design (`empire-ios/Shared/Design`), so a
  new app built from it has both from its first screen. Widgets follow the home screen. Rules and details:
  `empire-ios/CLAUDE.md` → Light mode.

## A new app touches (checklist)

An app's identity is still written by hand in several places across the repos, and nothing checks that they agree
(council 2026-10-25: the Empire app could not open Arestoteles because one of them was missed). Go through this list
for every new app:

- **empire-ios:** the project from `scripts/new-app-project.py` (bundle id `de.ares-empire.<slug>`, the shared
  Keychain group and App Group); `EmpireAppIdentity.all` and `AppAccent` in `Shared/`; its URL scheme
  (`CFBundleURLTypes`); the screenshot launch arguments in `Shared/AppRoot.swift`; its String Catalog and privacy
  manifest; its entry in `docs/APP-STORE.md`.
- **Hub (`ares-empire`):** its entry in `webauth/apps.json` (the URL scheme; its install link once there is a
  TestFlight public link, later the App Store link: [API-EMPIRE.md → Apps](API-EMPIRE.md#apps); since 2026-10-25 the
  one place for both, replacing `APP_SCHEMES` in `webauth/server.py`); the province in `web/app/empire-data.js` and in
  the server's `data/state.json` (and a chronicle line in both); `webauth/catalog.json` if other accounts may ask for
  it.
- **Accounts:** the service name in the account server's `services`/`requested` options and `NAMES`
  (`accounts/pb_hooks/lib/accounts.js` and a migration). An app that holds only Patrik's data also gets the owner list
  `EMPIRE_ALLOWED_USERS` in its server (like Aresium, Arestoteles, Aresus), so approving a request cannot open it.
- **Push:** the app-to-service map ([PUSH.md](PUSH.md)), if it sends notifications.
- **Its server:** `DELETE /api/<service>/me` and the internal deletion route if it keeps data per account; its data
  in the nightly backup if it cannot be rebuilt ([BACKUP.md](BACKUP.md) → New data); its province in Aresus
  (`aresus/checks.yaml`); the server's Aresync `REPOS` and a deploy hook.
- **Privacy:** its row in [PRIVACY.md](PRIVACY.md), and its section in the public policy before anyone but Patrik gets
  it.
- **Its contact form on the web**, once others can get it: one form for asking for the app and for questions, in the
  app's look, on its website (as Aresium's aresium.de/contact), or on the hub for an app without one (as Arestemis's
  www.ares-empire.de/arestemis/contact; [ACCOUNTS.md](ACCOUNTS.md) → Website contact form → A new app's form); then its
  "get the app" links (patrikbreeck.com `content/apps.json` → `request`, the hub's demo) point there.


- A new build stays installable for 90 days. We ship updates far more often than that while
  building, so it does not run out. Uploads can be automated later (Xcode Cloud is included
  with the membership, or a script on the Mac).
- Updating on the phone: open TestFlight, tap *Update* (TestFlight can also update automatically).
- Sharing with friends later: add them as external testers (invite link, first build reviewed
  once), with their own Empire account.

## Order of work

1. Empire accounts on the server ([ACCOUNTS.md](ACCOUNTS.md)), just Patrik for now. ✅
2. Aresium accepts an Empire login for its API (`/api/data`, `/api/transaction/…`, `/api/import`). ✅
3. Aresium: move the dashboard calculations from the browser (`web/public/app/data.js`: month totals,
   balances, chart series, category totals) to the server, so `/api/data` sends ready numbers and the
   website and the app only display them ([EMPIRE.md → How we build apps](../EMPIRE.md#how-we-build-apps-web--ios)).
   Still one request per page load, so switching months stays instant (1,246 transactions on 2026-10-23:
   milliseconds on the server). Before switching, the old and new calculation must give identical numbers
   on the real data. Agreed 2026-10-23.
4. ✅ (simulator; TestFlight pending) `empire-ios`: the Aresium app (login, dashboard, transactions, recategorise, import via share
   sheet), then a widget. **Import stays in the app** (Patrik: very handy on the phone). **Template:** the
   mobile website (`aresium/web/public/app/mobile.jsx`) has the layout, gestures and spacing worked out;
   the SwiftUI screens follow it, compared side by side on the simulator (mobile site in the simulator's
   Safari vs the app).
5. Later: Aresium for other people, their data on their iPhone, not the server (decided 2026-10-25; EMPIRE.md → Now and next).
6. ✅ (simulator; TestFlight pending) The Empire itself on the phone: [EMPIRE-APP.md](EMPIRE-APP.md) (throne room, per-user ring, approvals).
7. ✅ (simulator; TestFlight pending) Arestemis ([ARESTEMIS-APP.md](ARESTEMIS-APP.md)) and Aresus with Aresync
   ([ARESUS-APP.md](ARESUS-APP.md)), on one push service for all apps ([PUSH.md](PUSH.md)), 2026-10-24.

## Links

- Apple: [Compare memberships](https://developer.apple.com/support/compare-memberships/) ·
  [TestFlight overview](https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview) ·
  [Add internal testers](https://developer.apple.com/help/app-store-connect/test-a-beta-version/add-internal-testers) ·
  [Unlisted app distribution](https://developer.apple.com/support/unlisted-app-distribution) ·
  [Enrollment](https://developer.apple.com/de/support/enrollment/)
