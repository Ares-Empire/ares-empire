# Aresync drop: from the phone to the MacBook — plan

**Draft 2026-11-01** (Claude, for Patrik), with Patrik's answers from the same evening in "Decided".

**Status (2026-11-02):** **it works on the phone.** Patrik's first file (a PDF to Sort later) landed on the Mac on
2026-11-02 with Aresus build 2, after macOS gave `/usr/bin/python3` Full Disk Access (switching on Python.app does not
count: macOS checks the launcher the agent starts). Built since: delete any drop with a swipe (server: `DELETE` in any
state), the push says "<name> delivered", new folders made in the picker where you browse, the sheet closes with one
swipe (aresus brief 92, empire-ios brief 93, Aresus build 3). In progress: Aresus in the iPhone's share sheet with the
send screen inside it, uploads in a background session that go on after the share sheet closes, dropping files onto
the Aresync tab, a second pick adding to the first (empire-ios briefs 94 merged, 100 the look). Receipts (step 2)
come after. Server: `~/aresus`; Mac: `~/aresync`; app: `empire-ios/Aresus` (its Aresync tab). Replaces
`empire-ios/CLAUDE.md` → Open 11 ("Aresync file sharing from the phone").

## What it is

Send any file or photo from the iPhone to the MacBook, from anywhere. It lands in the folder Patrik picks, under the
name he picks, or in one fallback folder that says "this still needs sorting". Receipts go into the receipts folder
(Rechnungen) with their line in its `INVENTORY.md`. A push says where each file landed.

No Claude session sorts anything. The Mac only does a few fixed things: create a folder, write the new file under a
checked name, add a receipt's inventory line.

## Decided (Patrik, 2026-11-01)

- **Through the server, not git.** Git would keep every photo in history forever, and the repos must stay
  publishable (no personal data in any repo).
- **In Aresus's Aresync tab**, plus the iPhone's share button. Aresus and Aresync stay Patrik's own tools.
- **Targets: Documents and Downloads** on the MacBook, nothing else.
- **A fallback folder** when nothing was chosen, nothing fitted, or the chosen folder no longer exists:
  `Documents/Zu sortieren` (made on first use; Claude's pick of name and place, Patrik can rename it in the Mac's
  config).
- **Patrik picks folder, new folder and name** on the phone; suggestions only fill these in, he confirms.
- **Receipts go into Rechnungen and get their `INVENTORY.md` line**, including whether the receipt is for the
  Steuererklärung.
- **Windows laptop: later or never.** Not in this plan.

## What it builds on

- **Aresus server** (`~/aresus`, Python, `/api/aresus/*`): Empire login for the app (owner only,
  `EMPIRE_ALLOWED_USERS`), one **machine token** per machine for Aresync's run reports (`docs/API.md` there), push to
  the owner through the Empire push service ([PUSH.md](PUSH.md)).
- **Backups** ([BACKUP.md](BACKUP.md)): the server encrypts with **age** to the Mac's public key; the secret key is in
  the Mac's Keychain. The drop uses the same method with a key pair of its own (below).
- **Aresium's receipt reader**: the phone reads a scanned receipt with Vision (`Aresium/Model/ReceiptCapture.swift`),
  and the engine's `readReceipt` (`Aresium/Engine/aresium-engine.js`, built from `~/aresium`) turns it into shop, date
  and total. Nothing of it is kept.
- **Arestemis's AI** (Groq, `openai/gpt-oss-120b`, `~/Arestemis/src/arestemis/llm/`), for step 3 only.
- **The receipts folder's own rules** (`CLAUDE.md` in Rechnungen): the file name
  `YYYY-MM-DD Händler - Artikel - Betrag EUR.pdf` (no umlauts, no slashes), the retention table, and when a receipt
  goes to `Permanent/`. The Mac program follows those rules in code; it reads the folder's path from the Mac's config.

## How a file travels

1. **Phone:** pick the file(s) or photo(s), the folder, optionally a new folder inside it, and the name. Send. Without
   a connection the phone keeps it and sends later (as Arestoteles does with notes). The tab shows it as
   "waiting for the MacBook".
2. **Server (Aresus):** checks the owner's login and a size limit (start: 200 MB per file), **encrypts the file on
   arrival** with age to the drop key's public half, and stores it with its target. It never keeps it unencrypted on
   disk.
3. **Mac (Aresync):** a small program of its own (`drop`, its own launchd agent, every 60 seconds while the Mac is
   awake; separate from the sync run at load and 09:00) asks the server for waiting drops with its machine token,
   downloads, decrypts with the drop key from the Keychain, checks the target (rules below), writes the file, and
   reports where it landed.
4. **Server:** deletes the file once the Mac has reported, and sends a quiet push: "In Rechnungen:
   2026-11-01 Bauhaus - Bohrmaschine - 89,99 EUR.pdf". A file the Mac hasn't fetched after 7 days gets one reminder
   push; it stays until the Mac has it.

The **folder list** the phone picks from comes from the Mac: the program sends the names of the folders under
Documents and Downloads (no files, no hidden folders, nothing inside a git repo, `node_modules` or build folders, up to
4 levels deep) whenever they change, plus how many files wait in the fallback folder. The server keeps only the latest
list.

### The drop key

A new age key pair, made once on the Mac: the secret half in the Mac's Keychain ("Ares Empire drop key"), the public
half on the server next to Aresus. Separate from the backup key, so the program that runs every minute never needs the
backup key.

## Rules the Mac keeps

- **Only inside Documents and Downloads.** The target is a folder from the list plus an optional new folder plus a
  name. Never an absolute path; no `..`, no `/` in a name, no name starting with `.`; the file keeps its extension.
  A target that resolves outside the two roots, or into a git repo, goes to the fallback folder instead.
- **Never overwrites:** an existing name gets " (2)", " (3)" …
- **Never deletes, renames or moves anything that is already on the Mac.** It only adds the new file, and a new
  folder when one was asked for.
- **A folder that is gone** (renamed or deleted since the phone's list) → fallback folder; the push says so.
- **Problems reach Aresus** like a failed sync run (a push for a drop that could not be written), never silently.

## Suggestions, in three steps

Each step works on its own. Step 3 is built only if steps 1 and 2 leave too much to pick by hand.

1. **No AI.** Recent folders first, a search over the folder list, and the folder last used for the same kind of
   file (a receipt → Rechnungen, a PDF from Files → where the last PDF went). The name starts as the file's own name,
   with the date in front for photos.
2. **Receipts, still no AI.** "Receipt" on the send screen opens the iPhone's document scanner (or takes a photo),
   the phone makes a PDF and reads it with Aresium's reader: shop, date, total. Patrik types only the item (the
   optional "What is it" line). The name follows Rechnungen's pattern by itself. How Aresus gets the reader: the same
   engine build that Aresium uses, or a receipt-only build of it from `~/aresium` (decide when building; never a
   second copy of the reading logic).
3. **A free model for everything else (only if needed).** The phone reads the text in the file with Vision and sends
   only that text, the "What is it" line and the folder list to Aresus, which asks Arestemis's Groq model for a folder
   from the list (or the fallback), an optional new folder and a name. The file itself never goes to the AI. The
   server checks the answer against the list before the phone shows it. A wrong guess costs one tap.

The "What is it" line is optional everywhere. It helps when a file has no readable text (a photo of a thing), and for
receipts it is the item in the file name and the inventory line.

## Receipts

The send screen for a receipt shows what was read (shop, date, total; each can be corrected), the item, and four
choices:

| Choice | Default | Effect (from Rechnungen's rules) |
|---|---|---|
| For the Steuererklärung | off | date at least **31 December, five years after the purchase year** (decided 2026-11-01, also in Rechnungen's rules): the Finanzamt can ask back until the Festsetzungsfrist ends, 4 years from the end of the tax year when filing voluntarily, from the end of the filing year when filing is required (§ 169, § 170 AO). Five years covers both when a required return is filed the following year. |
| For the flat | off | → `Permanent/` (flat purchase, renovation and Handwerker invoices: proof for a later sale and the 10-year Spekulationsfrist) |
| Valuable, keeping it | **on above 500 €** | → `Permanent/` (value proof for a Hausrat claim while he owns it) |
| Manufacturer's warranty | none | years, or an end date: date at least warranty end + 1 month |

**The inventory line is written by code, not AI:** the rules are fixed, so the date is exact.

- **Normal receipt:** `Löschen ab` = receipt date + 24 months + 1 month; `Grund` says so in the folder's wording
  ("Gewährleistung 24 Mon. ab Lieferung … → …, + 1 Mon. Puffer …"), plus "Steuer" or the warranty when they set a
  later date. The latest date wins. `Noch im Besitz?` = ja.
- **`Permanent/`:** a row in the Permanent table, `Warum permanent` = "Wohnung" or "Wertnachweis, solange im Besitz".
- The row goes in sorted by `Löschen ab`, and the **Nächste Fälligkeit** line is updated.
- **If `INVENTORY.md` doesn't look as expected** (a column changed, the table can't be found), the Mac files the PDF,
  leaves `INVENTORY.md` untouched, and the push says the line is missing. The next session in the folder adds it.

There is **no separate Steuererklärung folder**: the receipt stays in Rechnungen, and "Steuer" in its `Grund` marks
it. At tax time, the rows that say Steuer are the list of what to claim.

## Privacy

Aresus and Aresync are Patrik's only and never go to others, so the privacy policy needs no new section. Drops and the
folder list are left out of the nightly backup: a drop lives on the server only until the Mac has it, and the list is
rebuilt by the Mac. In step 3 the text of a file goes to Groq, as Arestemis's listings do.

## Building it

Design by Claude, the rest by Codex (Patrik, 2026-10-31); each part checked before the next.

1. **Server** (`~/aresus`): drop storage with age, the app routes (send, list of my drops, folder list) and the Mac
   routes (folder list in, waiting drops, file, done), the reminder, the push. Contract in `docs/API.md` there.
2. **Mac** (`~/aresync`): the drop key, the `drop` program and its launchd agent, the target rules, the folder list,
   the receipt inventory line (with tests on a copy of the inventory's format, never the real folder).
3. **App** (`empire-ios/Aresus`): the send screen in the Aresync tab (design first), the share extension (files and
   photos), the waiting/landed list, the offline queue. Then step 2 (receipts). The share extension shows the send
   screen itself: iOS gives a share extension no way to open its app (Patrik agreed, 2026-11-02). The drop code lives
   in `Aresus/AresusDrops/`, compiled into the app and the extension; the queue is in Aresus's own App Group
   `group.de.ares-empire.aresus`.
4. **Live test** on the phone: a photo, a PDF from Files, a receipt for each choice, a vanished folder, the Mac asleep
   for a night.
5. Step 3 only after a few weeks of use, if picking by hand is too much.

## Later, if wanted

- **The other way round:** a folder on the Mac whose files appear on the phone (a ticket, a document needed while
  away). "Find my files" would fit here.
- **Links and text** from the share button (as a file, or into the Arestoteles inbox).
- **A receipt into Aresium too**, matched to its bank payment.

## Not planned

- The Windows laptop (Patrik, 2026-11-01: later or never).
- Renaming or moving files that are already on the Mac.
