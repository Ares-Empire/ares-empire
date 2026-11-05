# Planning council: reach and wake

2026-11-05 evening · subject: an extension of the work board ("The Council" in `EMPIRE.md` → Expansions), as written
in the seats' shared brief at ares-empire `27edba0` · a planning council (`docs/COUNCIL.md`), the first with a
cross-check round · about 25 minutes. Builds on the first planning council over the board:
`empire-ios/docs/reviews/2026-11-03-work-board-council.md`.

**The idea:** any Claude session on any of Patrik's machines (MacBook, Windows laptop, server), and Patrik from his
iPhone, can reach any other session directly and wake it, also on a machine where no session runs. Claude's lead
proposal before the council: use Claude Code's own Remote Control and messages between running sessions, and build
only what they cannot do: a record that outlives sessions, Codex, the Empire app's Decisions tab, and a small
always-on program per machine that watches the board and starts a session.

**Why now:** the laptop's keyboard got a stuck key (Deskflow passed it on to the Mac too). Patrik could only type
from his phone into a Mac session, which could not reach any session on the laptop: they showed as "Remote Control ·
offline". The message went across by the clipboard instead.

| Seat | Role and question | Model |
|---|---|---|
| A | Evidence: how often was reaching or waking really needed, and what did it cost? | Claude (subagent) |
| B | Future use: which planned features would be better with it, and which only sound good? | Claude (subagent) |
| C | System: what works on each machine and state, what breaks, how is it kept safe, what does it cost? | Claude (subagent) |
| D | Skeptic: what is the cheapest way to most of the value; should anything be built? | Claude (subagent) |

Round 1 blind, round 2 each seat checked the other three. Full answers stay local.

## What the history shows (seat A, corrected in round 2 by B)

- **Between sessions on one machine, messages work and are used a lot:** about 60 sent between 2026-10-31 and 11-03,
  none held or lost. Examples: an alert to a live fix in 12 minutes, a contract change to a live server change in
  25 minutes, four sessions paused for the repo swap and resumed in 14 minutes.
- **Across machines: the MacBook and the server talked once, in both directions** (the repo swap on 11-02: two
  messages, three replies within about 14 minutes). **No session on the Windows laptop has ever answered a message:**
  one from 11-02 is still queued, and today failed the same way. Both times the laptop's session was running but not
  connected to Remote Control.
- **Patrik carried messages by hand about 5 times in 10 days**, usually a minute each. Built-in messages cover all but
  one once the laptop's sessions are connected.
- **Waking a closed session or a sleeping machine: needed 0 times.** On 2026-11-01 Patrik said he does not want the
  sync to start a Claude session.
- **Work that stopped and nobody noticed: 2 cases** (an interrupted turn idle for about 6 hours; the MacBook's battery
  ran out and it stayed off for about 10.5 hours). Reach or wake would have fixed neither; an alert that a machine went
  silent would have caught the second.
- **The real pain in messages is knowing which session is which:** broadcast rounds of "ignore this if you are not the
  X session", and one session known by two names on two machines.

## What all seats agree on

1. **The always-on program per machine already exists in Claude Code:** `claude remote-control` in server mode stays
   running, keeps one session open and starts more on demand, from the phone or by a message to its session, and serves
   a crashed session again when it gets a message. Writing our own would rebuild it. The lead's proposal was wrong on
   this point.
2. **Today's failure was a connection problem on the laptop, not a missing feature.** Diagnose it there first
   (`claude --version`, `/status`, `/list-agents`) and test one message each way (Mac → laptop, phone → laptop).
3. **`crossSessionInbound: "accept"` on every machine.** It is not set on the MacBook or the server. Without it, a
   message between sessions in different permission modes waits for an approval nobody sees and is dropped after
   5 minutes.
4. **Claude Code 2.1.318 or later on every machine.** Before it, server mode fails to start new sessions after an
   auto-update until restarted (the MacBook has 2.1.317, the server 2.1.311).
5. **Name sessions by role** (`--name`, `/rename`), so messages reach the right session on every machine.
6. **Every message across machines carries a date and an "ignore after" condition.** A queued message can arrive days
   later, and a session that skips permissions would act on it.
7. **Turn on Trusted Devices** for Remote Control: Face ID again after 18 hours, and a lost phone can be cut off.
8. **Never build:** our own channel for live messages, waking sleeping or switched-off machines, free text from the
   board fed into sessions that skip permissions, typing into terminals by faked keystrokes, a reach field in the
   Empire app (the Claude app's Code tab already is one), or a way to wake Codex (Codex ends about 2026-11-20).

## Settled in the cross-check

- **The doorbell's mode:** Patrik's own user on the MacBook and the laptop, mode `auto` (risky steps come to the phone
  for approval; a message can never approve anything), in a trusted folder outside every synced repo, under a
  supervisor that restarts it (a LaunchAgent with KeepAlive on the Mac, a task at logon on Windows). Not the mode that
  skips permissions: an always-on doorbell in that mode would let any session misled by a web page drive another
  machine with nobody watching.
- **Server mode on native Windows is not confirmed** by the docs or the changelog. Test it on the laptop before relying
  on it.
- **A doorbell needs a health line:** an always-on program can fail quietly for days. Its status goes to Aresus.
- **A second way into the laptop that does not depend on Claude:** OpenSSH, key only, home network only (A, B, D).
  Today it would have let the Mac session fix the laptop directly.

## Where the seats still disagree (for Patrik)

1. **The work board itself.** A (after round 2) and D: not justified yet. What the history shows (stale "running"
   lines, one clash over a new file's name with no work lost, one power loss, one missed question) costs minutes, and
   session names and dated messages fix most of it; 8–12 days of build would compete with work that has a deadline.
   Cheapest step instead: each brief's state read from its result file and git (about half a day). B: the board can go
   ahead as the 11-03 council planned. C: no position on the board itself.
2. **A doorbell on the server.** B: now. C: wait until an Aresus incident goes unhandled because no Mac session could
   be reached. D: never with the server's full rights; Mac sessions already reach the server over SSH.
3. **A program that picks up board decisions.** C: not planned, but revisit if at least 3 decisions in two weeks wait
   more than 12 hours because no session ran on the target machine. A, B, D: the doorbell plus `claude --resume <id>
   --bg` covers that without a program of our own.

## General case (all seats)

Patrik is the switchboard and the only lasting memory between many short-lived agents on several machines, and no
machine has a reliable way in from outside. What has worked so far is one reachable session per machine, writing
state where the next agent looks (git), and removing dependencies between machines (the gallery drawn on the Mac),
not a message system of our own.

## Outcome: verdict for Patrik

**Reach and wake: don't build.** Set up what Claude Code already has (about 1–2 hours, no code), then one small
aresync brief:

- **Now, no code:** the laptop's Remote Control diagnosed and tested; `crossSessionInbound: "accept"` and 2.1.318+
  on all three machines; Trusted Devices on; sessions named by role; dated messages; OpenSSH on the laptop.
- **One aresync brief:** the supervised doorbell on the MacBook (and the laptop once the test passes), with health
  lines to Aresus, plus an alert when a machine goes silent.
- **Wait, with triggers:** the work board's decision record until two decisions are lost because their session ended;
  file claims until a clash costs lost work or two merge repairs in a month; a server doorbell until an incident goes
  unhandled for lack of a reachable session; a decision pickup program on C's trigger above.

Open for Patrik: the three disagreements above. Once decided, the EXPAND entry in `EMPIRE.md` and
`web/app/empire-data.js` change to match.
