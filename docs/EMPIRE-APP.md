# The Empire on the phone — decision record

**Decided 2026-10-24** with Patrik. Status (2026-10-24): **built** — the phone website is live, the iPhone app
(`empire-ios/Empire`) works on the simulator; TestFlight waits for Apple (open items: `empire-ios/CLAUDE.md` → Open). Builds on [IPHONE-APPS.md](IPHONE-APPS.md) (native SwiftUI apps
in `empire-ios`, TestFlight) and [ACCOUNTS.md](ACCOUNTS.md) (Empire accounts in PocketBase).

## What the Empire is on a phone

1. **A launcher:** tap a province to open it: its iPhone app if installed, else its website (with that website's own
   login; Safari has no Empire login from the app), else the province's page (council 2026-10-25).
2. **Live status:** each province card says something live (e.g. Aresium: this month's spending; others: up or down).
3. **Approvals (Patrik only):** new sign-ups waiting for approval, approve or decline on the phone.
4. **One login for all:** log in once in the Empire app; the province apps (Aresium) use the same login
   (shared Keychain between the apps).

**iPhone features** ([IPHONE-APPS.md](IPHONE-APPS.md) → check for every app; Patrik, 2026-10-25): a notification
when a request is approved ("Whose ring shows what" below). Patrik gets sign-ups and access requests by email and
decides in Approvals, without notifications (Patrik, 2026-10-26). Every app now logs in and asks for access itself, so the
Empire app is the launcher, the chronicle, getting more apps, and (Patrik) approvals.

As for Aresium, the hub gets a **mobile website version first**: it is what phone browsers see and the template the
SwiftUI app follows (compared side by side on the simulator).

## Layout: "Throne room"

One home screen that keeps the desktop hub's identity, top to bottom:

- **Header:** crown mark left, **THE EMPIRE** in gold, right: EXPAND (Patrik only, icon) and log out; a small gold
  badge with the number of pending approvals (Patrik only) that opens **Approvals**. The marble bust as a faded
  backdrop behind the top of the screen.
- **The ring:** a swipeable row of province cards (the focused card large and lit, its neighbours peeking and
  dimmed, page dots below), like the desktop ring laid flat. A card: mark, GOLD NAME, status, one live line. Tap the
  focused card → it **opens** (the app, else the website; one that cannot open yet shows its page). **Hold** any card
  → the **province page** (about, features, what's new); there the mark and the name are the link, no Open button
  (Patrik, 2026-10-24, after trying the app; the website's phone version does the same).
- **Below the ring:** Patrik: the **CHRONICLE**; everyone else: **WHAT'S NEW**, the chronicle entries about the
  provinces in their own ring. Both as a vertical gold timeline (gold line on the left, bust markers, date · tag, text).
- **EXPAND (Patrik):** the ring shows the **EXPANSIONS** (plans) instead. Claiming new ground stays on the desktop.
- **Intro:** the slam intro as on the website.

## Whose ring shows what

| | Patrik (admin) | Everyone else |
|---|---|---|
| Ring | every province, always | **every app the account has access to** (its `services`), plus a **"+"** card at the end (Patrik, 2026-10-25) |
| "+" | — | the other apps **open to users** (the catalog Patrik controls), each with its state: *Ask for access* → *Asked, waiting for approval*; *coming soon* ones shown, not requestable |
| Below the ring | the full chronicle | "What's new" for their ring's provinces |
| Expansions, Approvals | yes | no |

**The catalog** is `webauth/catalog.json`, one entry per province open to users: `users: "open" | "coming-soon"`
(a province not listed is private). Today: Aresium `coming-soon` (it holds only Patrik's data until it becomes multi-user, a later project);
every other province `private` (Arestoteles has nothing for others, Aresync is two scripts, Arestemis is an
unactivated bot). A `coming-soon` province is shown in the "+" and cannot be asked for yet (2026-10-25; before, it
could be added to a saved ring).

**Access stays `services`, set by Patrik** (decided 2026-10-25, replacing the saved ring and its instant adding):
the ring shows what an account may use, so a friend approved for Arestemis sees Arestemis without adding it.

**Getting an app** (Patrik, 2026-10-25): in "+", *Ask for access* puts the app into the account's `requested`;
Patrik gets a notification (below) and approves; the person gets a notification that the app is ready, and it joins
their ring. Tapping an app in the ring opens it when installed, else its website, else its page with **Install**: the
app's install link from the hub (a TestFlight public link while in testing, the App Store link later; the link is
shown only to accounts that have the app).

**Notifications** (Patrik, 2026-10-25/26, the Empire app's iPhone features): an account gets one when a request is
approved ("Arestemis is ready"; they never see who asked for what). Patrik gets sign-ups and access requests by email,
not as notifications. Sent by the account server through the push
service; live once Apple's push key exists (the push service runs as a dry run until then).

## How it works underneath

- **PocketBase** (migration): the user field `admin` (bool): only a superuser sets it. Admins may list and view all
  users and set `approved`, `services` and `requested` on other accounts (and delete unapproved sign-ups). Approvals
  therefore run with Patrik's own token; no superuser password is stored on the hub or in an app. The saved `ring`
  (2026-10-24) was dropped on 2026-10-25 (migration `1793400000_drop_ring.js`): the ring is the account's `services`.
- **Hub server `GET /api/empire`** answers per account, so the website and the app only display:
  `me {id, name, admin}`, `projects` (the ring: admin → every province; others → the provinces in their `services`,
  each `access: "granted"` with its `install` link), `addable` (the "+": catalog provinces they do not have, each with
  the catalog's `state` and `access: "requested" | "none"`), `chronicle` (admin: all; others: entries about their
  ring's provinces), `ideas` (admin only), `pending` (admin only: number waiting, `null` when the account server could
  not say). Live lines come from the server too (it asks each province with the visitor's token; e.g. Aresium's month
  spending). The apps' URL schemes and install links are in `webauth/apps.json`.
- **Hub server actions:** ask for an app of the "+" (`POST /api/empire/request`, checked against the catalog); admin:
  list pending accounts, approve, decline. Same auth statuses as Aresium (401 / 403 / 503); every error also carries a
  `code` the app acts on ([API-EMPIRE.md → Errors](API-EMPIRE.md#errors), 2026-10-25).
- **Notifications:** the account server sends them through the push service next to its emails
  ([PUSH.md → Who sends what](PUSH.md#who-sends-what)).
- **One login for all** (iPhone): the Empire app and the Aresium app share the token in a Keychain access group;
  needs the paid team (pending).

## Order of work

1. ✅ **Mobile hub (website):** the throne room at phone widths, built against the `/api/empire` shape above with sample
   data for an admin and for a normal user. Look and feel decided on screenshots, then refined.
2. ✅ **Accounts + hub API:** the PocketBase migration (tested on a copy before the live server), per-account
   `/api/empire`, ring actions (replaced on 2026-10-25 by asking for access), approvals, live lines.
3. ✅ **Empire iPhone app** in `empire-ios` (simulator; TestFlight pending) (a second app target; shared code — login, API client, design tokens —
   moves into a shared folder now that a second app exists), following the mobile hub.
4. Later: multi-user Aresium; then flip Aresium to `open` in the catalog.
