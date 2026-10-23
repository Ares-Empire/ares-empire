# 01: The hub on a phone ("throne room")

Status: merged and live 2026-10-24. Data layer, dialogs, approvals and add flow by Codex; the look reworked by Claude after Patrik's feedback (approved).
Branch: `codex/01-mobile-hub` · Worktree: `../ares-empire-01-mobile-hub` · Model: `gpt-6.1-sol`, effort `high`

## Goal

Phones get their own version of the hub, as decided in `docs/EMPIRE-APP.md` ("Layout: Throne room", "Whose ring shows
what"). It is what phone browsers see and the template the Empire iPhone app will follow. Built against the per-account
data in `docs/API-EMPIRE.md` (version 2) using sample data; the server side comes in a separate brief.

## Read first

- `docs/EMPIRE-APP.md`, `docs/API-EMPIRE.md` (the contract: build exactly this shape), `EMPIRE.md` ("The crown
  language", "The hub").
- The hub today: `web/index.html`, `web/app/boot.jsx` (intro, mounting), `web/app/app.jsx` (data loading from
  `/api/empire` with the seed fallback), `web/app/ring.jsx`, `web/app/panels.jsx` (`Chronicle`, `ProjectDetail`,
  `CardGrid`), `web/app/brand.jsx`, `web/app/styles.css`, `web/app/empire-data.js` (seed), `web/app/empire-intro.js`.
- The model for "separate phone tree, shared data layer": `~/aresium/web/public/app/mobile.jsx` and how `app.jsx` there
  routes phones to it.

## Build

1. **Separate phone tree** `web/app/mobile.jsx` (`window.EmpireMobile`), mounted below a ~620 px breakpoint instead of
   the desktop scene (not a reflow of the desktop layout). The desktop hub stays exactly as it is.
2. **Data:** read `/api/empire` version 2 as the desktop does. Two sample files, `web/app/samples/empire.admin.json` and
   `web/app/samples/empire.user.json`, made from the seed in the version-2 shape (admin: all provinces, ideas,
   chronicle, `pending: 2`, a `live` line for Aresium; user: a ring with Aresium `coming-soon`, `addable: []` once it is
   in the ring, chronicle filtered to Aresium, no ideas). When opened from `file://` (no server), use the admin
   sample; `?as=user` switches to the user sample (sample mode only).
3. **Screens** (`docs/EMPIRE-APP.md` "Throne room"):
   - **Header:** crown mark, THE EMPIRE in gold (crown language: polished gold text, Space Grotesk caps, wide
     tracking), log out; admin: EXPAND as an icon button and a gold badge with `pending` that opens Approvals.
     The marble bust as a faded backdrop behind the top of the screen.
   - **Ring:** horizontally swipeable province cards, the focused one large and lit, neighbours peeking and dimmed,
     page dots; snap on release; keyboard arrows. Card: mark, GOLD NAME, status (admin: the martial status word;
     users: "coming soon" when `state` is `coming-soon`), `live` line if present. For non-admins, a last **"+"** card
     (dashed gold outline) opening the **Add sheet**: the `addable` provinces with mark, name, blurb, "coming soon"
     badge, and Add. Adding calls `POST /api/empire/ring {add}` and shows the returned data; in sample mode it
     updates the sample in memory. Remove a province from the ring from its page (non-admins).
   - **Province page** (tap the focused card): about, features, what's new (its chronicle entries), and **Open**:
     website via the existing hub hand-off for hand-off provinces, else the link. `coming-soon`: no Open, a short
     "coming soon" note.
   - **Below the ring:** admin: CHRONICLE; others: WHAT'S NEW. Vertical timeline: thin gold line on the left with the
     bust markers the desktop chronicle uses, date · tag, text, newest first.
   - **EXPAND** (admin): the ring shows EXPANSIONS (`ideas`) as cards; tapping one shows its detail. No forge on the
     phone.
   - **Approvals** (admin): pending accounts (email, name, signed-up date) with Approve / Decline (Decline asks for
     confirmation), via the routes in `docs/API-EMPIRE.md`; in sample mode two made-up accounts and local updates.
   - **Intro:** the existing slam intro plays on phones too (it already handles reduced motion).
4. **Look:** the crown language (near-black, polished gold used sparingly, Space Grotesk / JetBrains Mono, glass
   cards). It should feel like the desktop throne room made for one hand: generous touch targets (44 px), safe areas,
   no horizontal page scroll.
5. **Screenshots** at 402×874 with headless Chrome from `file://` (Chrome is installed:
   `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --headless=new --window-size=402,874
   --virtual-time-budget=9000 --screenshot=… file://…/web/index.html[?as=user]`; skip the intro for screenshots with a
   query flag that only works in sample mode): `build/01-admin-home.png`, `build/01-admin-expand.png`,
   `build/01-province.png`, `build/01-approvals.png`, `build/01-user-home.png`, `build/01-user-add.png`, and the
   desktop unchanged at 1440×900: `build/01-desktop.png`. `build/` is in `.gitignore` (add it if not).

## Settled: do not re-open

- Throne room layout, per-account content from the server, instant add, approvals admin-only, expansions admin-only,
  forge desktop-only. All in `docs/EMPIRE-APP.md`.
- No new dependencies; same React + Babel-standalone setup as the desktop hub.

## Out of scope

- `webauth/server.py`, PocketBase, the real API (next brief). The desktop layout. The iPhone app.

## Rules (no sandbox: these are rules, not walls)

Work only inside the worktree. Never commit, push or change git config (Claude commits). Install nothing. Network only
for the CDN scripts the hub already loads. No secrets or personal data in files; made-up accounts in samples.

## Done when

- The phone version works from `file://` in both sample modes, the desktop is unchanged, and the screenshots exist.
- Final message: files changed, how to switch modes, the screenshots, anything doubtful.
