# 03: Aresium for other people: privacy texts, the netcup AVV and Groq

Status: draft
Branch: `codex/03-aresium-privacy` · Worktree: `~/ares-empire-03-aresium-privacy` · Model: `gpt-6.1-sol`, effort `high`

## Goal

Aresium (the finance app) will open to a few of Patrik's friends. Get everything privacy-related ready before that:
the public policy's Aresium section in German and English (ready to insert, not live yet), the internal inventory, and
a clear answer to "does the processing agreement (AVV) with netcup need updating, and what else is legally needed",
including Groq as the AI provider. Patrik decides and clicks in the providers' panels; you prepare and check.

## Rules (this repo has no AGENTS.md; these apply)

- Work only in the worktree. Never commit, push, deploy, or touch the server or any other repo (Claude does that).
- Network: read public web pages only (curl or your search), for the provider facts below. Cite every external fact
  with its URL and the date you checked it. Never guess a legal fact; mark it as open instead.
- Plain English in docs; the public German text in the existing policy's style (neutral, "Sie", statements, no
  "ich"/"du"); English the same with "you". No personal data in any file.

## Read first

- `docs/ARESIUM-FOR-OTHERS.md` (the plan: phone mode, part 5 layer 3 "Auto-sort through our server", part 7, Decisions).
- `docs/PRIVACY.md` in full (the inventory, the rule for opening a province, Facts: the AVV with netcup and what was
  declared there, the Aresium section, To do 6).
- `web/legal/datenschutz.html`, `web/legal/privacy.html` (the live policy), `webauth/legal.py` (how pages are served:
  `DRAFT_MARKERS` stop a page from being served).
- `~/empire-ios/docs/APP-STORE.md` (read only: the App Store privacy answers).

## What Aresium for others processes (settled, from the plan)

- The app needs an Ares account (already covered by the policy).
- Imports, payments, categories and sorting rules stay on the person's iPhone; our servers never receive them, except:
- **Auto-sort** (optional, off by default, one switch; switching it on is the consent): payments the app could not sort
  itself are sent to a new Aresium server route at netcup (Germany): per payment the date, amount, booking text and
  counterparty, with a random reference, plus the person's category names. The server asks Groq (Groq, Inc., USA; model
  `llama-3.3-70b`), returns a category per payment, and stores nothing: no database row, no request body in any log.
  Groq's Zero Data Retention will be switched on. Rate-limited per account.
- Patrik's own Aresium data stays on the server as today (his own data, not in the public policy).

## Build

1. **Draft public sections** (not served yet): `web/legal/drafts/aresium.de.html` and `web/legal/drafts/aresium.en.html`,
   fragments in the exact markup and style of the live pages, plus the small changes elsewhere in each policy that the
   section needs (recipients: Groq; third-country transfers: the USA and its legal basis; legal bases; storage periods;
   right to withdraw consent), each as an exact "insert after / replace" instruction in
   `web/legal/drafts/README.md`. Check in `webauth/legal.py` that nothing under `drafts/` is served; say so.
   Content: what stays on the phone (and that we cannot see it), what auto-sort sends, to whom, why, legal basis
   (consent, Art. 6(1)(a) GDPR; and whether Art. 9(2)(a) explicit consent is needed because booking texts can reveal
   health, religion or union membership: give your reasoning), no storage, withdrawal by switching it off, that it is
   optional.
2. **Netcup AVV check:** compare what was declared to netcup (PRIVACY.md → Facts: affected persons, data types, "no
   bank, payment or financial data") with the new processing (financial data passing through the server without being
   stored). Answer: does the AVV need updating; if yes, the exact entries to add in netcup's customer panel (Stammdaten
   → AV-Vertrag), in German as netcup's form words them if you can find the form's categories publicly.
3. **Groq check:** from Groq's own pages: its data processing terms (DPA: does one exist, how it is concluded, is it
   part of the terms), retention by default and with Zero Data Retention, where data is processed, sub-processors,
   whether Groq, Inc. is certified under the EU-U.S. Data Privacy Framework (check the official list at
   dataprivacyframework.gov) and so what the transfer's legal basis is (adequacy decision or the standard contractual
   clauses in its DPA), and whether API data is used for training. Start at https://console.groq.com/docs/your-data and
   https://console.groq.com/docs/legal.
4. **Anything else required?** Give a short reasoned answer for each: a record of processing activities (Art. 30, and
   whether the 30(5) exemption applies to a private project like this), a data protection impact assessment (Art. 35,
   and the German DSK list), whether the App Store privacy label changes (Apple counts data as "collected" only when it
   is kept longer than needed to answer the request in real time: quote Apple's definition and say what Aresium's label
   should be), and anything you find that the plan missed.
5. **Docs:** `docs/PRIVACY.md`: the Aresium section gets the processing for others (internal inventory style), To do 6
   is replaced by a numbered opening checklist (insert the drafts, AVV entries, Groq DPA and ZDR, App Store answers,
   the server route's no-logging check), and a new section "Opening Aresium: legal check (2026-10-26)" with your
   findings from 2–4 and their sources.

## Settled: do not re-open

- Auto-sort goes through our server and Groq (Patrik, 2026-10-26); no on-device model.
- The public text goes live only when Aresium opens to others (the policy describes what really happens; it does not
  name Aresium today). Nothing in the live `datenschutz.html` / `privacy.html` changes in this brief.

## Done when

- The drafts and README exist; `docs/PRIVACY.md` is updated; `python3 -c "import ast,sys; ast.parse(open('webauth/legal.py').read())"`
  still passes (you do not need to change legal.py; if drafts would be served, say so instead of changing it).

## Final message

Files changed; the AVV answer (yes/no and the exact entries); the Groq findings with URLs; the answers to 4; anything
you could not confirm.
