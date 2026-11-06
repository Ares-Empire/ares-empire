# Planning council: the work board (session record, decisions, communication)

2026-11-05 night · subject: "The Council" in `EMPIRE.md` → Expansions as planned by the first council
(`empire-ios/docs/reviews/2026-11-03-work-board-council.md`): a shared board for every Claude and Codex session on
every machine, with a session record, decisions for Patrik in an app tab, and communication between sessions on top
of Claude Code's own messages · a planning council (`docs/COUNCIL.md`) with a cross-check round · about 35 minutes.

**Given, not argued again:** Claude Code's Remote Control and messages between sessions are on for every machine since
2026-11-05 (`remoteControlAtStartup`, `crossSessionInbound: "accept"`, version 2.1.318). Running sessions reach each
other and Patrik reaches any of them from the Claude app. The question was what a board adds on top. An earlier
council the same evening (`2026-11-05-reach-and-wake.md`) was focused on reaching and waking sessions by mistake; its
remarks on the board are replaced by this record.

| Seat | Role and question | Model |
|---|---|---|
| A | Evidence: with messages working, where does work across sessions still go wrong, and what would a board prevent? | Claude (subagent) |
| B | Patrik's side: how does he decide and keep track today; would a Decisions tab help or be one more inbox? | Claude (subagent) |
| C | Future: what should the board become as the Empire grows, what is a trap, where should it live? | Claude (subagent) |
| D | Skeptic: the strongest case against, and the cheapest structure that still gets the value | Claude (subagent) |

Round 1 blind, round 2 each seat checked the other three. Full answers stay local.

## What the history shows

- **Live coordination works.** About 60 messages between sessions from 10-31 to 11-03 settled contracts between
  repos, merge order and the repo swap within minutes. No bug Patrik reported since 10-30 came from a missed contract.
  Since 11-04 sessions are split by area and barely message each other.
- **What goes wrong happens when no session is watching** (all four seats found the same cases on their own):
  - **Finished work that never ships.** Work built on 11-03 still sat unmerged or uncommitted two days later,
    including a fix against lost edits and a backup fix. Brief status lines said "running" for work that was merged
    or finished; they were corrected on 11-03 and one was wrong again within a day.
  - **Questions for Patrik buried when a session's attention moves on.** On 11-03 and 11-04 the lead session asked
    Patrik five things at the end of long replies; he answered other parts, nobody asked again, and two days later
    all five were open. The session did not end; it moved on. About 25 items wait for Patrik across 8 or more places
    (repo Open lists, review records, HANDOFF files, memory files, gitignored run results, quiet sessions); 8–10 of
    them have consequences.
  - **Brief numbers** agreed by message clashed three times (11-01, 11-02, 11-03) and the ranges live only in one
    machine's memory; one range is nearly used up.
  - **Not knowing which session is which:** broadcast rounds of "ignore this if you are not X", a message to the
    wrong session.
- **Hand-written status drifts everywhere:** about seven places hold status today, the chronicle exists in three
  copies that disagree, and some overview files have grown into build logs thousands of words long.
- **How Patrik decides:** in live chat he answers within minutes, mostly from the Claude iPhone app, and in about
  half of the decision lists he first asks back what an item means. Questions at the end of long reports get missed.

## What all seats agree on

1. **The 11-03 plan is too big and aimed at the wrong things.** Drop:
   - the session registry and heartbeats: Remote Control and the agent view already list live sessions, and every
     session starts in the home folder and runs for days across several repos, so a hook would record no repo or
     branch;
   - file claims and edit hooks: clashes cost minutes, never lost work;
   - the Codex launch wrapper: Codex ends about 2026-11-20;
   - a separate service with its own database, the board's own discussion threads, a progress feed, a chronicle
     written from the board;
   - a messaging layer of our own: role addressing is solved by naming sessions, and a "message to a future session"
     is an open item;
   - agents taking work from the board, and any free text from the board reaching sessions that skip permission
     prompts.
2. **Status is derived, never written by hand:** a scan of every Empire repo (unmerged branches, worktrees with
   uncommitted files, brief status lines that contradict git, each with its age), shown at every session start
   whatever its folder.
3. **One private place for what waits on Patrik:** decisions with fixed options and **owner actions with due dates**
   (new compared with 11-03). The open "for Patrik" lines move there and are deleted from repo Open lists, memory
   and HANDOFF files, or the board becomes one more copy. Sessions add items on purpose (a small `ask` command), never
   scraped from transcripts. Private, because the public repos must not list security-relevant open items.
4. **A brief-number ledger** (a file, not the board), and **sessions named by role.**
5. **The phone part, when built, lives in Aresus,** not the Empire app and not the sync run log: Aresus is
   owner-only and already has machine tokens, push, its own database pattern (drops: waiting → done or failed, with a
   receipt) and the fix for crashes on notification taps. Sync log lines are not a phone path: quiet runs fold away
   and lines sit three taps deep. Patrik said on 11-03 the board "should be part of the Empire app"; that stays his
   call.
6. **An item on Patrik's list is short:** the question first, why, what waits on it, the options, at most about 60
   words. Answers are a tap, Done, or "Ask in Claude", a link to the asking session (`claude.ai/code/session_<id>`;
   whether iOS opens it in the Claude app is unverified). At most one quiet push a day, only for something with a
   deadline or older than 24 hours.

## Where the seats disagree (for Patrik)

**The phone screen: now, or after a trial?**
- **B and D: now** (about 3–4 days in total). Lines printed at session start reach Claude, not Patrik, who reads on
  his phone; and sessions run for days, so a new session starts rarely. The five buried questions already meet D's
  own trigger (3 items waiting more than 48 hours in one week).
- **A and C: after a trial** (about 1.5 days now): the scan and the private list first, shown at every session start;
  the Aresus tab if, within two weeks, an item with a deadline or one that blocks work sits more than 48 hours unseen.
  The hard part of an `ask` screen is deciding what goes on it.

## General case (all seats)

The Empire writes its state down, but in many hand-kept copies that nobody is prompted to read, and every copy
drifts. The gap is bringing work and open questions back up once a session moves on, and giving them an owner, not
communication between sessions. The fix is fewer places: derive what git knows, and keep the rest in one list.

## Found on the way (outside the board)

- Finished fixes from 11-03 not yet merged or deployed (lost edits in Arestoteles; a backup gap), and briefs that
  exist only in a gitignored folder on one machine.
- A suspected aresync push bug was checked and is not live: it needs a git setting no machine has.
- Aresus shows a laptop that has been silent for 3 days only as inactive, with no alert.
- "The Watchtower" is still listed as an expansion although Aresus has been it since 2026-10-24.

## Outcome: verdict for Patrik

**Build smaller, and widen in one direction.** Instead of the 11-03 plan (a new service, 8–12 days):

1. **Now, about 1.5 days, private:** the derived scan, the private list of decisions and owner actions with due dates
   (with the open lines moved into it), the brief-number ledger, sessions named by role.
2. **The Aresus "Waiting on you" tab** (about 1.5–2 days more): now (B, D) or after the trial (A, C).
3. **Never:** the parts listed in agreement 1.

Open for Patrik: the timing of the phone screen, and Aresus or the Empire app as its home. Once decided, the EXPAND
entry in `EMPIRE.md` and `web/app/empire-data.js` change to match.

## Patrik's decisions (2026-11-06)

- **The phone screen comes now, in Aresus.**
- **Open work goes to its session first.** A session that finds open work belonging to another topic (a fix waiting
  to merge, a question that session asked) sends it to that topic's session instead of putting it on Patrik's list.
  Only what needs his own decision or action reaches him. In the global CLAUDE.md since 2026-11-06.
- **Sessions name themselves:** `name-me <topic>` (aresync `claude/name-me`) turns `name-me aresium` into
  `mac-aresium` from the next prompt on; a name Patrik gave stays. Live on the MacBook and the server since
  2026-11-06. The topic in the name is how open work finds its session.
- The five buried questions are closed.

## The design that follows (briefs 232 and 233)

Because the phone screen comes now, the list lives in Aresus from the start instead of a file in a private repo
that Aresus would have to copy. The brief counter lives there too: one counter on the server cannot hand out a
number twice, a file edited on three machines can.

- **One list, two kinds of items, each with a topic.** *Asks* need Patrik: a decision with fixed options, or an
  action, with a due date when there is one. *Work* belongs to a topic: found by the scan, or left by a session for
  the next session on that topic.
- **Where items go.** Work never goes on Patrik's screen. A session that names itself gets its topic's work; a
  session that sees work for a topic whose session is running sends it there and marks it sent (at most once a day
  per item). Asks go to the Aresus tab; the answer reaches the asking session with its next prompt, or else the next
  session on that topic. Work whose topic has had no session for two days shows on Patrik's screen as one line with
  a count, not as questions.
- **The scan** runs with every aresync run on the MacBook and the server: branches not merged, worktrees with
  uncommitted files, commits not pushed, each with its age and its repo as topic. Its items close by themselves when
  git no longer shows them. Brief status lines are left out of the first version: comparing their free text with
  git is guesswork, and the branch and worktree checks find the same cases.
- **A `board` command** (aresync) for sessions: the topic's items, ask, leave work for a topic, mark sent or done,
  take the next brief number. A start hook prints the counts at every session start.
- **The Aresus tab "Waiting on you":** the asks, question first; one tap answers, marks done, or opens the asking
  session in Claude; at most one quiet push a day, only for an ask due within two days or unanswered for a day.
