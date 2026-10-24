# Aresus on the phone — decision record

**Decided 2026-10-24** with Patrik. Status: being built. Server: the new `aresus` repo (API contract: `docs/API.md`
there); app: `empire-ios/Aresus`. Push: [PUSH.md](PUSH.md).

## What it is

Aresus, the watchtower province, combined with Aresync in one **iPhone app** (no website), with two tabs:

- **Aresus:** every province, one below the other, as a box like the hub's (mark, name, one short status word):
  **Issue** (red) at the top, then **Active** (green), then **Inactive** (grey; "Planned" for provinces not built yet).
  A province with an issue also sends a push. Tap a box for its checks, last deploy and recent incidents. A small
  server line (disk, memory, uptime) sits above the list.
- **Aresync:** the sync runs of every machine (MacBook, Windows laptop, server) and whether they worked. A failed sync
  sends a push; Aresync's Telegram alerts retire once push works on the phone.

## Decisions

- **Aresus decides from its own checks**, never from the hub's status words (those are unreliable for now, Patrik
  2026-10-24). Each province declares in `checks.yaml` whether it is meant to run: off on purpose (Arestoteles,
  Aresis) is **Inactive**; meant to run but failing is an **Issue**. A check must fail twice in a row (about 2 minutes)
  before it counts, so a restart does not wake anyone.
- **Checks per province:** systemd units, Docker containers, timers, HTTPS answers (status and time), TLS certificate
  expiry, and the deployed commit (and whether GitHub is ahead). The server itself: disk, memory, load, uptime.
  Backups are not checked yet (Patrik will set backups up later).
- **Push:** when an issue opens (time-sensitive) and when it is fixed (quiet). Aresync pushes exactly when its Telegram
  alert would fire today: immediately for a rebase conflict, a failed deploy hook or the privacy guard; for network-type
  failures only once they have lasted an hour. The app shows every failed run in red right away.
- **Aresync reports every run** to Aresus (`POST /api/aresus/sync/runs`, one token per machine, never failing the
  sync itself). The server syncs every 5 minutes, so the tab shows the machines first and then only runs that did
  something or failed; quiet runs collapse into one line per machine and day.
- **Server deploys through Aresync** (Patrik approved auto-deploy, 2026-10-24): the server's Aresync also pulls
  `Arestemis`, `aresus` and `aresync` and runs a hook that restarts the service, plus the missing hook for the hub.
- **Who may use it:** accounts with the `aresus` service (Patrik decides).
- **Accent colour: lightning blue** (Zeus), only as an accent, which also keeps green and red free for the status
  words. Icon: the Zeus bust on black; the Aresync tab uses the Janus bust.
- Later: Aresus can give the hub's Empire app a live line per province (up/down), and a home-screen widget.
