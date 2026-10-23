# The Empire on the phone — decision record

**Decided 2026-10-24** with Patrik. Status: planned. Builds on [IPHONE-APPS.md](IPHONE-APPS.md) (native SwiftUI apps
in `empire-ios`, TestFlight) and [ACCOUNTS.md](ACCOUNTS.md) (Empire accounts in PocketBase).

## What the Empire is on a phone

1. **A launcher:** tap a province to open it: its iPhone app if installed (Aresium), else its website, already logged in.
2. **Live status:** each province card says something live (e.g. Aresium: this month's spending; others: up or down).
3. **Approvals (Patrik only):** new sign-ups waiting for approval, approve or decline on the phone.
4. **One login for all:** log in once in the Empire app; the province apps (Aresium) use the same login
   (shared Keychain between the apps).

As for Aresium, the hub gets a **mobile website version first**: it is what phone browsers see and the template the
SwiftUI app follows (compared side by side on the simulator).

## Layout: "Throne room"

One home screen that keeps the desktop hub's identity, top to bottom:

- **Header:** crown mark left, **THE EMPIRE** in gold, right: EXPAND (Patrik only, icon) and log out; a small gold
  badge with the number of pending approvals (Patrik only) that opens **Approvals**. The marble bust as a faded
  backdrop behind the top of the screen.
- **The ring:** a swipeable row of province cards (the focused card large and lit, its neighbours peeking and
  dimmed, page dots below), like the desktop ring laid flat. A card: mark, GOLD NAME, status, one live line. Tap the
  focused card → the **province page** (about, features, what's new, an Open button).
- **Below the ring:** Patrik: the **CHRONICLE**; everyone else: **WHAT'S NEW**, the chronicle entries about the
  provinces in their own ring. Both as a vertical gold timeline (gold line on the left, bust markers, date · tag, text).
- **EXPAND (Patrik):** the ring shows the **EXPANSIONS** (plans) instead. Claiming new ground stays on the desktop.
- **Intro:** the slam intro as on the website.

## Whose ring shows what

| | Patrik (admin) | Everyone else |
|---|---|---|
| Ring | every province, always | only the provinces in their own ring, plus an empty **"+"** card at the end |
| "+" | — | lists the provinces **open to users** (the catalog Patrik controls); adding is **instant** |
| Below the ring | the full chronicle | "What's new" for their ring's provinces |
| Expansions, Approvals | yes | no |

**The catalog** is a field per province in the empire data: `users: "open" | "coming-soon" | "private"` (default
private). Today: Aresium `coming-soon` (it holds only Patrik's data until it becomes multi-user, a later project);
every other province `private` (Arestoteles has nothing for others, Aresync is two scripts, Arestemis is an
unactivated bot). A `coming-soon` province can be added; its card then says "coming soon" and does not open.

**Adding to the ring never grants access to a province's data.** Access stays `services`, set by Patrik.

## How it works underneath

- **PocketBase** (migration): two new user fields.
  - `admin` (bool): only a superuser sets it. Admins may list and view all users and set `approved` and
    `services` on other accounts (and delete unapproved sign-ups). Approvals therefore run with Patrik's own token;
    no superuser password is stored on the hub or in an app.
  - `ring` (list of province slugs): the user may edit their own.
- **Hub server `GET /api/empire`** answers per account, so the website and the app only display:
  `me {id, name, admin}`, `provinces` (the ring as this account sees it: admin → all; others → their `ring` ∩
  catalog, each with `state: "open" | "coming-soon"`), `addable` (catalog minus their ring), `chronicle` (admin: all;
  others: entries tagged with their ring's provinces), `ideas` (admin only), `pending` (admin only: number waiting).
  Live lines come from the server too (it asks each province with the visitor's token; e.g. Aresium's month spending).
- **Hub server actions:** add or remove a province in your own ring (checked against the catalog); admin: list
  pending accounts, approve, decline. Same auth statuses as Aresium (401 / 403 / 503).
- **One login for all** (iPhone): the Empire app and the Aresium app share the token in a Keychain access group;
  needs the paid team (pending).

## Order of work

1. **Mobile hub (website):** the throne room at phone widths, built against the `/api/empire` shape above with sample
   data for an admin and for a normal user. Look and feel decided on screenshots, then refined.
2. **Accounts + hub API:** the PocketBase migration (tested on a copy before the live server), per-account
   `/api/empire`, ring actions, approvals, live lines.
3. **Empire iPhone app** in `empire-ios` (a second app target; shared code — login, API client, design tokens —
   moves into a shared folder now that a second app exists), following the mobile hub.
4. Later: multi-user Aresium; then flip Aresium to `open` in the catalog.
