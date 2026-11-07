# Security, privacy and data-loss sweep (review council, 2026-11-07)

**Kind:** Review (`docs/COUNCIL.md`). **Asked by:** Patrik, 2026-11-07, after about 90 Arestemis briefs, Aresium's
public TestFlight and arestemis.de's "Ask for access" since the last security review (brief 219, 2026-11-03).
**Outcome: Corrected.** No finding changes what gets built or why; none was critical. Two small decisions went to
Patrik (below).

## Subject (frozen)

Everything merged to `main` after the brief-219 review (last commit before 2026-11-03 18:50) up to the morning of
2026-11-07:

| Repo | Range | Public |
|---|---|---|
| ares-empire | `2e6d8c3..4167c1d` (36 commits) | yes |
| aresium | `c79cb57..1d9577a` (15) | yes |
| Arestemis | `afab162..49a0346` (200; schema 13 → 24) | no |
| Arestoteles | `1c93f73..5b803d1` (5) | yes |
| aresus | `22a6ded..eb31554` (4) | no |
| aresync | `13d3603..a2cd6db` (15) | no |
| empire-ios | `fd07445..f05ee3c` (96) | yes |
| ares, AresOS | `4aa623c..04104c7`, `f1bc6aa..4690074` (tiny) | yes |

Scope: someone reading other people's data through a server, login and token flaws, personal data in the public
repos and logs, the privacy policy against the code, silent data loss (failed writes, backups, migrations), injection,
SSRF in the readers, secrets in logs. Not style, refactors or features. Seats read code only: no requests to the live
servers, no `.env` files, keys or live databases.

## Seats

All Codex `gpt-6-astra`, effort high, read-only (`-s read-only`), blind round then a cross-check round on the same
session (each seat got the other four answers and checked them against the code).

| Seat | Role | Question |
|---|---|---|
| S1 | Security: Arestemis | Can an account holder, or someone who controls a page Arestemis reads, make the server do what it should not (access between accounts, SSRF, untrusted content, AI providers)? |
| S2 | Security: the shared core | Can an outsider or another account use accounts, hub, push, contact forms, Aresus or Aresync to reach what is not theirs, or lock Patrik out? |
| S3 | Security: Arestoteles, Aresium, iPhone apps | Where does untrusted input reach something it should not in code other people now run? |
| S4 | Privacy | What personal data or secrets are where they should not be, and does the privacy policy match the code? |
| S5 | Data loss | Where can data that cannot be rebuilt be lost, or a write fail, without anyone being told? |

Also run: the Aresync privacy guard (`privacy-check.sh --all`: the private-terms list plus gitleaks) over the full
history of all six public repos: clean.

## Findings and what happened

Severity after the cross-check and Claude's own reading of the code. Details that would help an attack stay out of
this file until fixed; the seats' full answers are kept locally.

| # | Finding | Sev. | Outcome |
|---|---|---|---|
| S1-2 | Arestemis: one account could add wrong prices to a price history other accounts read | medium | fixed, Arestemis brief 247 `ad875bb`: barcode identities sent by the app get a history of their own; schema 25 copied every curve before retiring the shared keys |
| S1-3 | Arestemis: AI work started by saving searches skipped the per-account allowance and could hold up other accounts | medium | fixed, brief 247 `ad875bb`: saved work counts against its own per-account allowance at background priority, accounts take turns |
| S1-1 | Arestemis: some page text could make fact reading slow on the loop the API shares | low–medium | fixed, brief 247 `ad875bb`: fact text capped at 8,192 characters, long digit and space runs dropped, the IKEA scrub moved to the parser worker |
| S4-2 | Privacy policy: "no seller names are stored", but listing descriptions can contain one | medium | fixed, ares-empire `00425ac` (both languages, PRIVACY.md) |
| S4-3 | Privacy policy: Cloudflare answers whenever Groq cannot, not only when its daily allowance is used up | low | fixed, `00425ac` (wording; the fallback stays) |
| S5-4 | Arestemis evaluation labels and test sets were in no backup | low | fixed, `00425ac` (backup lists and BACKUP.md) |
| S4-1 | empire-ios: a public brief and CLAUDE.md named a real receipt file and quoted a purchase wish | medium | fixed in current files, empire-ios `34953f4`; history: question 2 |
| S2-1 | Accounts: leaving an app could, in the same moment as an administrator's change, write back an app the administrator had just taken away | low | fixed, ares-empire `9f1e28b` (one transaction, unit test) |
| S5-1 | Drops: after the server's drop database starts afresh (it is outside the backup on purpose), the Mac could confirm a new drop as an older one and the new file was deleted unread | high impact, rare | fixed, brief 246: the Mac acknowledges only a landed file whose size and SHA-256 match (aresync `3015727`); a fresh drops database starts its ids at the current time in milliseconds (aresus `12b4097`) |
| S2-2 | Aresync: two runs started together after a crashed run could both run | low–medium | fixed, brief 246, aresync `3015727`: an OS lock released when the run ends, never held by its children (macOS and Linux; the Windows script keeps its own lock, which has the same rare race) |
| S3-2 | Aresium engine: a crafted Excel file inside the size limits could expand far beyond them | medium | fixed by mac-aresium-import, aresium `4bf74ed` (budgets for cells and table text while the sheet grows); build 25 went only to Patrik, testers get build 26 with the fix |
| S5-3 | Aresium engine: a ZIP with two statements could merge two bookings that only look alike | low–medium | fixed, aresium `4bf74ed` (a repeated id with a different balance is refused) |
| S3-1 | Arestoteles: the overall sign-in cap can be used up by others and keep the owner out of the website login for a while (not the app) | medium | fixed, Arestoteles `93da0ea`: Patrik chose to drop the shared cap (the access key is long and random); 10 tries per address stay, tracked per address with bounded memory |
| S5-2 | Drops waiting for the Mac are in no backup, and the phone lets go of its copy once the server has it | low | accepted, documented in BACKUP.md: the database is outside the backup on purpose, files wait minutes (days while the Mac is off), and the original stays where it was shared from |

**Checked and fine** (so the next review can skip it): Arestemis route ownership for hunts, matches, saved, recently
viewed, not checked, settings and applications; internal routes only on localhost; every user-typed address still
through the guarded fetcher, and the catalogue readers limited to fixed sites with checked redirects; AI answers can
only pick among offered candidates; AI usage rows hold counters, not prompts or keys; the hub and push request limits
of brief 220 (deadlines, sizes, worker bound, rightmost forwarded address from a trusted proxy only); access-job
collections superuser-only and their targets fixed; contact forms rate-limited, plain-text mail, no read access;
`?look=` and contact topics allow-listed; push device ownership; the work board's routes behind machine tokens or the
owner, parameterised SQL, no board text run by a shell; backup restore rejects traversal and links; the new SQLite
tables (board, push fences, AI usage) inside backed-up databases, SQLite copies through the backup API; Arestemis
migrations transactional with the version; Arestoteles API owner check before the body, 128 KiB cap, note names
sanitised, versions checked; the iPhone apps build authenticated requests only from fixed Empire hosts; the Arestemis
web demo uses made-up data; the new Aresium fixtures and sorting tests use made-up payments.

**General case.** Most findings are one pattern: a protection added at one boundary (the API, a worker, a field, a
per-address limit, a backup list) that a newer path does not pass through (a background job, a shared cache, a parser
before the worker, a global counter, a database outside the backup). Worth asking of every new path: which of the
existing guards does this pass?

**Could not check:** the live Caddy configuration, firewall, environment, deployed versions and installed hooks;
whether portals accept the input lengths some scenarios need; TestFlight binaries.

## Questions for Patrik

1. **Arestoteles website login (S3-1):** keep the overall cap? It is what limits guessing from many addresses, and
   others can use it up and keep the owner out of the website login (not the app) for a while. Advice: drop
   it if the access key is long and random, keep it if it is memorable. (Board #39.)
2. **empire-ios history (S4-1):** the receipt file name and the purchase quote stay readable in the public history.
   Advice: no fresh-repo swap for these alone; bundle them with the older real file name already in that history if one is ever done.
   (Board #40.)

**Found on the way** (not a code finding, corrected the same day): the Mac's drop agent refuses about one pass in five
with "no access to documents". The cause is not a lost permission: on macOS `/usr/bin/python3` and `/usr/bin/git` are
the same Xcode helper binary under two names, and after git has run, macOS sometimes credits the drop agent to
`/usr/bin/git`, which has no Full Disk Access (seen in the TCC log, `responsible_path=/usr/bin/git`). The next pass
works, so drops arrive a minute later; all four drops so far landed and none were waiting. Fix: see board.

## Cost

Round 1 about 6 % of the weekly Codex allowance (5 Astra seats), round 2 about 3 %, brief 246 (`gpt-6.1-sol`, high) a
few more; about 2½ hours from start to the last merge. Claude: planning,
verifying each finding in the code, two small fixes, the record.
