# Arestoteles app — decision record

**Decided 2026-10-24 (Patrik).** Arestoteles stops being a trading bot and becomes the iPhone app for Patrik's
Weltbild: his Obsidian vault of topics, positions, mechanisms, events and questions (`~/Documents/Patrik Breeck/
Weltbild`, repo `carlsenares/opinions`, rules in its own `CLAUDE.md`). The website arestoteles.de stays as it is.

## The decisions

- **Read fast, offline:** the app answers "what do I think about X, and why?" in a few taps. Start screen: the
  positions; each opens the chain behind it (mechanisms, events, sources). Topics as a reader (summary boxes first),
  the library (mechanisms with every place they appear, events as a timeline by year and region, questions, actors),
  search over everything incl. the English–German glossary, and a briefing per topic before a discussion.
- **Edit in the app** (Patrik asked for it): the server applies each edit by the vault's own rules, so the map stays
  his thinking. Structured edits for what the phone is good at: confirm a draft position, reword it, change or drop a
  view (the old one goes to "How my view changed", never overwritten), add a position, set a note's confidence, adopt
  or dismiss one of Claude's callouts. A free Markdown editor for everything else, and a quick note into `Inbox/`.
- **Discuss with Claude, no API key:** a Discuss button hands the topic to the Claude app, where Claude Code works on
  the vault repo with its `CLAUDE.md`, like on the laptop, on Patrik's subscription. Tested 2026-10-24: a session
  from the phone pushes straight to `main`. No AI inside the app.
- **Two repos, on purpose:** the vault (`carlsenares/opinions`, content) and `Arestoteles` (code: the server, the
  website). Content and code have different lives: note edits must not deploy the server, the vault syncs between the
  laptops through Obsidian, phone Claude sessions should see only the vault and its rules, and the code can go public
  one day while the vault stays private. The vault's name must not start with "ares" (the empire sync would make it a
  province).
- **Sync:** the server keeps its own clone (`/var/lib/arestoteles/vault`, deploy key with write access, added
  2026-10-24), pulls every minute, commits app edits as "Patrik Breeck (Arestoteles app)" and pushes. The laptops get
  them through the Obsidian Git plugin (pull on open, push every 10 minutes); Aresync stays out of the vault (two
  committers on one repo would conflict).
- **The trading code is deleted** (Patrik: no use for it; git keeps the history). Kept: the website (`web/`,
  `webauth/`, its container and quote refresher).
- Accounts: the `arestoteles` Empire service (migration `1793000000_service_arestoteles.js`), given to Patrik and the
  test account. API: `Arestoteles/docs/API.md` (version 1), samples made up, never Patrik's notes.
- iPhone features (IPHONE-APPS.md checklist): a widget with a position to revisit, the notes in iPhone search
  (Spotlight), links `arestoteles://note/<id>`. Not now: Siri, Live Activities, on-device AI.
- Languages: the app in English and German; the vault's content as written (English with German terms).
