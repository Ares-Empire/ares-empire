# Languages — decision record

**Decided 2026-10-24 (Patrik):** every Empire app speaks **English and German**, the current ones and every future one.
A new app has both from its first screen; no screen ships in only one of them.

## Which language an app shows

- By default the iPhone decides: German when the phone puts German before English, otherwise English (the fallback
  for every other language).
- **Each app's Settings → Language** chooses for that app: like the iPhone, English or Deutsch. It is the same setting
  as iOS's own per-app Language (Settings → Apps → *the app*), which iOS only shows when the phone lists two or more
  languages (tested on iOS 27, 2026-10-24); so the apps offer it themselves (Patrik asked "how do I switch?", the
  earlier "no switch in the apps" rule is replaced).
- Choosing another language asks first, in the language it switches to ("Switch to English?" / "Auf Deutsch
  umstellen?"), with Cancel in the current one, then the app restarts inside itself in that language (Patrik,
  2026-10-25): back on its main screen, the servers' sentences and the device's notification language switch with it,
  and its widget follows. Words iOS draws itself inside the app (the Cut/Copy menu on selected text) follow at its next
  launch.

## What is translated

Everything the app or a server writes **as part of the interface**: titles, buttons, labels, hints, empty states,
errors, status words and lines, summaries, notifications, and the AI's notes about a listing.

**Not translated:** what people or other services wrote (listings, applications, transactions and their categories,
commit subjects, log lines), names (Aresium, WG-Gesucht, provinces), and the hub's chronicle and province texts: they stay English, also
inside the German apps (Patrik, 2026-10-24: not worth writing every entry twice).

## How it reads

- English is the source language: code, keys, samples and docs stay English; German is a translation of every string.
- German says **du**, in the same plain register as the English (no slogans, no anglicisms where a German word is
  usual). Terms people use in German stay theirs: WG, Kaltmiete/Warmmiete, Zwischenmiete.
- Numbers, money and dates follow the language: "€1,400" / "1.400 €", "Sat 24 Oct" / "Sa. 24. Okt.",
  24-hour times in both.
- German runs about a third longer. Every screen is looked at in German before it is merged; labels that wrap get
  a shorter word, not a smaller font.

## How the servers know

The language follows the app, so a server never stores a "user language" setting. One exception: the account's
`language` ([ACCOUNTS.md](ACCOUNTS.md#accounts-in-every-app)), which the app sends at sign-up, for the emails that
come later without a request to take the language from (the approval email). PocketBase's own verification and
password-reset emails are fixed templates that cannot follow a field: they carry both languages.

- **Requests:** every app sends `Accept-Language: de` or `en` (the language it shows). A server that writes sentences
  for the app answers in that language; anything else means English. The hub passes the language on when it asks a
  province for its live line.
- **Text kept for later** (an incident, the AI's reason for a match): stored so it can be shown in either language,
  as a message key with its values, or for AI text both languages from the same AI call. It is put into words when
  it is sent, in the language of that request.
- **Notifications:** each device registers its language with the push service ([PUSH.md](PUSH.md)); a province sends
  the English text plus the German one, and the push service picks per device.

## Websites

The websites (hub, Aresium) stay English only (Patrik, 2026-10-24). Their API calls send `Accept-Language: en`, so a
German browser still gets English from the servers.

## Where the details live

- iPhone apps: `empire-ios/CLAUDE.md` → Languages (String Catalogs, formatting, tests, screenshots in German).
- Each service's API doc names the fields it writes in the requested language.
