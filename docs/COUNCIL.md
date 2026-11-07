# Councils

A **council** is a few fresh agents, called seats, who look at the same subject at the same time. Each seat has its
own role and its own question. They answer without seeing each other, then each seat checks the others' answers, and
Claude puts the result together for Patrik. A council finds what one reviewer misses: one reviewer noticing a deeper
problem is luck, while several seats with different questions make it likely. It also checks that we are building the
right thing, not only that the code does what the plan says.

This is the method for every Empire repo. Taken from nametbd3 (`docs/REVIEW.md` there), which took it from nametbd;
Patrik added the cross-check on 2026-11-05 ("each agent has a different role and focus, and they check each other's
work afterwards"). Repos add their own triggers and focuses: `empire-ios/docs/REVIEW.md` for the iPhone apps.

## Two kinds

| Kind | Subject | Question |
|---|---|---|
| **Review** | something built or written: a commit range, a brief, a decision draft | Is it right, and is it the right thing? |
| **Planning** | an idea before anything is built | Is there a real need, and what is the smallest useful version? It must be free to say "don't build it". |

## When to run one

| Trigger | Example |
|---|---|
| A choice that is hard to undo | login and tokens, a data model, an API contract, something that can start programs on Patrik's machines |
| A milestone | before the first TestFlight build, before other people get an app, before a service goes public |
| The same kind of bug shows up twice | two fixes in one area that each caused the next |
| Agents have built a lot since the last look | every 2–3 weeks, over everything merged since |
| An expansion is about to get a plan | before the first brief of a new idea from EMPIRE.md → Expansions |
| Patrik asks | any time |

Not for: one screen's layout, mechanical changes with good tests, or a question a decision record already answers.
Quote the record instead. If Patrik wants to revisit it, that is a conversation, not a council.

## How big

Every seat needs **its own named question**. If you cannot say what one seat would find that the others would not,
drop the seat.

| Size | When |
|---|---|
| **2** (default) | an ordinary design question or a periodic sweep |
| **3–4** | login, tokens, money or personal data, a planning council over a new expansion |
| **5** (maximum) | before other people get it, or before going public |

Mix vendors when Patrik agrees: Claude agents plus Codex (`codex exec -s read-only -m <model>`, usually `gpt-6-astra`;
pick per task as the global CLAUDE.md says). Different models
miss different things. When he asks for Claude agents, use only Claude.

## Roles to pick from

Every seat answers the **general case** too: is this one instance of a wider problem? One sentence, even if the
answer is no.

- **Evidence:** what really happened? Counts real cases in briefs, run outputs, reviews and the Chronicle. A use case
  seen once is an anecdote.
- **Future use:** which planned or likely features would use it, in which concrete moment, and how often?
  Which only sound good?
- **System:** how would it work on each machine and service, what breaks, what does it cost to run, how is it kept
  safe?
- **Skeptic:** what is the cheapest way to get most of the value? Does something that already exists cover it?
- **Goal:** does it serve what the repo is for, and does it match the decision records?
- **Security and privacy:** secrets, tokens, what a stolen phone or a leaked key could do, personal data in public
  repos.
- **API boundary:** does the client match what the service really sends (read the service code, not the brief)?

## How to run it

1. **Freeze the subject:** a brief, a plan, a decision draft or a commit range. Write down the commit. Read earlier
   records on the same subject (`docs/reviews/` in the repos it touches) so the council builds on them.
2. **Write one shared brief** and one short block per seat. The shared brief holds the subject, what the repo is for,
   facts already checked, where to look, and the rules: read-only, no messages to other sessions, no personal data,
   mark each claim as checked or assumed. Each finding takes the form: what is wrong · why it matters · what to change
   · blocks or not.
3. **Round 1, blind:** run the seats in parallel. Claude agents with the Agent tool (general-purpose, in the
   background); Codex with `/opt/homebrew/bin/codex exec -s read-only -m gpt-6-astra -c
   model_reasoning_effort=high -o <file>`.
4. **Round 2, cross-check:** give each seat the other seats' answers. Continue the same agent (SendMessage) so it keeps
   what it read. Each seat checks: claims that are wrong or unchecked (it opens the source), where it disagrees and
   why, what the others found that changes its own verdict, and what everyone missed. This round is short.
5. **Claude reconciles:** what the seats agree on, the disagreements that matter, and the verdict. Where seats still
   disagree on substance, or a seat says the subject is the wrong thing to build, Patrik gets the disagreement in a few
   lines and decides.
6. **Save** to `docs/reviews/YYYY-MM-DD-topic.md` in the repo the subject lives in (`ares-empire/docs/reviews/` for
   subjects across the Empire): subject and commit, seats with role and model, findings, outcome, roughly how long it
   took. Seats' full answers stay local (`codex-runs/` or a scratch folder); public repos get no personal data.

## How it ends

A **review** council ends in one of two outcomes:

- **Corrected.** The fixes do not change what gets built or why: a bug, a missing test, an unnamed risk. Claude applies
  them and work goes on.
- **Redesign.** The outcome or the scope is wrong, or a decision record is contradicted. Work stops and the question
  goes to Patrik.

The test between them: **does the change alter what gets built, or why?** If yes, it is a redesign.

A **planning** council ends in one verdict for Patrik to accept or change: **build** (the smallest useful version and
its order), **wait** (for a named trigger that would make it worth building), or **don't build** (and why).

The cross-check in round 2 belongs to the council. After the outcome there is no second council over the fixes.

An accepted finding becomes a change in the code, the data or the docs, plus a test where it is code. A finding that
lives only in the review file did not happen.
