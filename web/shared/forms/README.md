# Shared contact form

The Ares apps' contact pages on the web are one form in different looks (Patrik, 2026-10-30 and 2026-11-01): Aresium's
(aresium.de/contact), the Ares Empire's (www.ares-empire.de/contact) and Arestemis's (www.ares-empire.de/arestemis/contact),
each also in German and each with `?topic=access` for asking for the app. What they share lives here, once:

| File | What |
|---|---|
| `contact-form.js` | The sending: checks, the topic's placeholder and note, the counter, problems, the sent state. Knows no app or language; reads everything from the page's data attributes (its header lists them). |
| `contact-form.css` | The layout, built from custom properties that each app's look sets for dark and light (its header lists the markup). |
| `SHA256SUMS` | The hashes of both, as `sha256sum` writes them. |

What each page has of its own: its markup and words (aresium `src/web/contact-page.ts`; here `webauth/contact.py`, which
writes the same markup) and its look (aresium `web/public/forms/contact.css`; here `web/contact/empire.css` and
`arestemis.css`, with `web/contact/hub.css` for the hub's look switch).

## Copies

aresium.de serves its own files, so aresium has byte-identical copies in `web/public/forms/` (`contact-form.js`,
`contact-form.css`). Both repos test them against the hashes:

- here, `webauth/test_contact.py`: the files match `SHA256SUMS`, and when an aresium checkout sits next to this one
  (`../aresium`, or `ARESIUM_DIR`), its copies are the same bytes;
- in aresium, `src/web/contact-page.test.ts`: its copies match the hashes it pins, and those equal this `SHA256SUMS`
  when the ares-empire checkout sits next to it.

## Changing them

1. Change the file here, then `sha256sum contact-form.css contact-form.js > SHA256SUMS` in this folder.
2. Copy both files to aresium `web/public/forms/` and put the new hashes into `SHARED_FORM_SHA256` in aresium
   `src/web/contact-page.test.ts`.
3. Run both repos' tests, look at every page that uses them (all three, light and dark, phone and desktop), and deploy
   both: the hub serves the change at once, aresium.de after its own deploy.

A new property in `contact-form.css` needs a value in every look; both repos' tests name a look that misses one.
