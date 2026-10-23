# iPhone apps — decision record

**Decided 2026-10-23.** Status: planned, first app = **Aresium**.

## The decision

- Empire services become **real native iPhone apps** (SwiftUI), not website wrappers.
  Native is what makes widgets, Face ID and other iPhone features possible later.
- Patrik gets the **paid Apple Developer Program** membership (99 USD/year, shown in EUR at
  sign-up). The free Apple ID route was rejected: those apps stop opening after 7 days and
  need a re-install from the Mac every week.
- Apps are installed through **TestFlight**, not the public App Store.
- The apps log in with an **Ares Empire account** from day one (see [ACCOUNTS.md](ACCOUNTS.md)),
  even while Patrik is the only user, so sharing later is a server-only change.
- Code lives in one repo for all iPhone apps: **[`empire-ios`](https://github.com/Ares-Empire/empire-ios)**.
  Each app talks to its service's existing API; the services stay where they are.
- iPhone work happens with **Claude Code on the MacBook** (Xcode only runs on macOS), so
  Claude can build, run the simulator and fix errors directly. Server work stays on the server.

## Verified facts (checked 2026-10-23 against Apple's docs)

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

## What this means in practice

- A new build stays installable for 90 days. We ship updates far more often than that while
  building, so it does not run out. Uploads can be automated later (Xcode Cloud is included
  with the membership, or a script on the Mac).
- Updating on the phone: open TestFlight, tap *Update* (TestFlight can also update automatically).
- Sharing with friends later: add them as external testers (invite link, first build reviewed
  once), with their own Empire account.

## Order of work

1. Empire accounts on the server ([ACCOUNTS.md](ACCOUNTS.md)), just Patrik for now.
2. Aresium accepts an Empire login for its API (`/api/data`, `/api/transaction/…`, `/api/import`).
3. `empire-ios`: the Aresium app (login, dashboard, transactions, recategorise, import via share
   sheet), then a widget.
4. Later: Aresium for several users (each person's data separated on the server).

## Links

- Apple: [Compare memberships](https://developer.apple.com/support/compare-memberships/) ·
  [TestFlight overview](https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview) ·
  [Add internal testers](https://developer.apple.com/help/app-store-connect/test-a-beta-version/add-internal-testers) ·
  [Unlisted app distribution](https://developer.apple.com/support/unlisted-app-distribution) ·
  [Enrollment](https://developer.apple.com/de/support/enrollment/)
