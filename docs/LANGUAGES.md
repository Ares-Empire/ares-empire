# Languages — decision record

**Decided 2026-10-24 (Patrik):** every Empire app speaks **English and German**, the current ones and every future one.
A new app has both from its first screen; no screen ships in only one of them.

## Which language an app shows

- The iPhone decides: the phone's language (Settings → General → Language & Region), or the app's own language
  (Settings → Apps → *the app* → Language, which iOS offers by itself once an app has two languages).
- German when the phone puts German before English, otherwise English. English is the fallback for every other language.
- No language switch inside the apps: iOS already has one per app.

## What is translated

Everything the app or a server writes **as part of the interface**: titles, buttons, labels, hints, empty states,
errors, status words and lines, summaries, notifications, and the AI's notes about a listing.

**Not translated:** what people or other services wrote (listings, applications, transactions and their categories,
commit subjects, log lines), names (Aresium, WG-Gesucht, provinces), and for now the hub's chronicle and province
texts, which are written in English (translating them means writing every entry twice; Patrik decides).

## How it reads

- English is the source language: code, keys, samples and docs stay English; German is a translation of every string.
- German says **du**, in the same plain register as the English (no slogans, no anglicisms where a German word is
  usual). Terms people use in German stay theirs: WG, Kaltmiete/Warmmiete, Zwischenmiete.
- Numbers, money and dates follow the language: "€1,400" / "1.400 €", "Sat 24 Oct" / "Sa. 24. Okt.",
  24-hour times in both.
- German runs about a third longer. Every screen is looked at in German before it is merged; labels that wrap get
  a shorter word, not a smaller font.

## How the servers know

The language follows the app, so a server never stores a "user language" setting.

- **Requests:** every app sends `Accept-Language: de` or `en` (the language it shows). A server that writes sentences
  for the app answers in that language; anything else means English. The hub passes the language on when it asks a
  province for its live line.
- **Text kept for later** (an incident, the AI's reason for a match): stored so it can be shown in either language,
  as a message key with its values, or for AI text both languages from the same AI call. It is put into words when
  it is sent, in the language of that request.
- **Notifications:** each device registers its language with the push service ([PUSH.md](PUSH.md)); a province sends
  the English text plus the German one, and the push service picks per device.

## Websites

This decision is for the iPhone apps. Whether the websites (hub, Aresium) get German too is open (Patrik decides).

## Where the details live

- iPhone apps: `empire-ios/CLAUDE.md` → Languages (String Catalogs, formatting, tests, screenshots in German).
- Each service's API doc names the fields it writes in the requested language.
