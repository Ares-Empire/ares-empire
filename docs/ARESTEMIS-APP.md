# Arestemis on the phone — decision record

**Decided 2026-10-24** with Patrik. Server: `Arestemis` repo (API contract: `docs/API.md` there);
app: `empire-ios/Arestemis`. Push: [PUSH.md](PUSH.md).

**Status (2026-10-24): built.** Server live (`arestemis.service`, `/api/arestemis/*`), app on the simulator, tested
live with a test account; push waits for the Apple key (PUSH.md).

## What it is

Arestemis (formerly FlatSniper) watches the flat portals and is first to a new listing. Until now it was a Telegram
bot with one search in a config file, stopped since Patrik found his flat. It becomes an **iPhone app** (no website):

- **Set the search in the app:** fields for everything measurable, plus one optional "anything else" text.
- **Start and pause the hunt** in the app.
- **Push notifications** for new matches (no Telegram), with "Open listing" and "Application" actions.
- **Listings overview:** every match with its facts, the portal link, and states new / saved / applied / dismissed.
- **Application text:** a setting: *my own text* (written once) or *written by AI for each listing* (from the listing,
  Patrik's own text as the base, and "about me").
- Later (not now): hunts for other things than flats. The core object is therefore a **hunt** with a `kind`
  (`"flat"` today); nothing generic is built beyond that. **2026-11-01:** that time has come; plan:
  the Arestemis repo, `docs/ARESTEMIS-ANYTHING.md`.

## Decisions

- **Fields, not free text, for the search** (Patrik: "lots of it can be deterministic"). **Simplified the same day**
  (API version 2, Patrik: the three kind buttons and the tiers were too fiddly): Flat or WG / Flat / WG, people moving
  in, max flatmates, size ranges (the flat; the room of a WG), places with optional areas, cold and warm rent ranges,
  move-in window and temporary offers, portals, and the "extras" text (furnished goes there). **Every filter is
  optional on its own** (it only changes how many listings pass); only a place and a portal are required. "Describe
  it" (a line that opens a sheet) fills the fields from a sentence; the fields stay the one source of truth.
- **The AI checks every listing against the whole search** (Patrik: many listings did not fulfil the filters). Two
  stages: (1) the fields are checked on the portal's structured data (exact, cheap); (2) every listing that passes is
  checked by the AI against the whole search **and** its full text (cold rent shown as warm, short sublets, flat
  swaps, WGs listed as flats, "women only", a move-in date only in the text, the "anything else" wishes). Only a pass
  is a match. Each match keeps the AI's one-line reason; rejected ones stay visible for 7 days with their reason
  ("Filtered out"), so a too-strict search shows.
- **Places Germany-wide by search-as-you-type**, not a dropdown: suggestions come from WG-Gesucht's own city list via
  the server, so every city offered can actually be searched; each city is mapped to each portal's id when chosen.
  The app says which portals cover a place.
- **Per account from the start** (a hunt and settings belong to an Empire account with the `arestemis` service),
  although only Patrik uses it. Not in the hub catalog yet (private).
- **The old search and data are deleted** (Patrik: he won't hunt for a flat for years). The new database starts empty.
- **Applications are never sent automatically.** The app shows the text to copy, then opens the listing.
- **Push replaces Telegram.** Until push works on the phone (paid Apple account pending), the server can also send
  matches to the old Telegram chat for one account (`TELEGRAM_FALLBACK_USER`); then that is removed.
- **AI:** Groq (`openai/gpt-oss-120b`; `llama-3.3-70b-versatile` was retired). All prompts stay in
  `llm/provider.py`.
- **Accent colour: moonlight violet** (Artemis wears a crescent moon), used only as an accent. Icon: the Artemis bust
  on black.
- **Deploy:** the server checkout moves from `/root/flatsniper` to `/root/Arestemis` so Aresync keeps it current and
  restarts `arestemis.service` after a pull (Patrik approved auto-deploy, 2026-10-24).
