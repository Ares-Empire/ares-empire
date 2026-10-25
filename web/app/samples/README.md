# Hub previews

Start a local preview from the worktree:

```sh
cd web && python3 -m http.server 8765
```

- http://localhost:8765/?skipIntro — the admin: every province, the expansions, approvals.
- http://localhost:8765/?as=member&skipIntro — a member with one app (Arestemis, with an install link) and the **+**.
- http://localhost:8765/?as=new-member&skipIntro — a member approved just now: an empty ring, only the **+**.
- http://localhost:8765/?as=requested&skipIntro — a member who asked for Arestemis and waits for approval.

At widths up to 620 px it mounts `window.EmpireMobile`; wider windows keep the
desktop scene. Omit `skipIntro` to play the slam once per session (unless reduced
motion is enabled).

Sample mode works only on `localhost` or `127.0.0.1`. It fetches the selected JSON
fixture; sample actions (asking for an app, approving, declining) update memory and
reloading resets them. Other hosts, including ares-empire.de, always use `/api/empire`
with session cookies and ignore `as` and `skipIntro`. The phone requires version 2
and shows a retry/login state on failure. The desktop keeps its seed fallback and
rendering. `file://` is unsupported.

The JSON files are the hub server's own answers, written by
`python3 tools/empire_samples.py --web` (made-up accounts, a made-up catalog with
Arestemis open and Aresium coming soon, one made-up install link; the provinces,
expansions and chronicle are the seed). Do not edit them by hand: run the command
again after a change to the contract or the seed; `tools/test_empire_samples.py`
fails while they are out of date. Accounts in the approvals preview are fictional
`example.com` accounts.

To preview asking for an app: open `?as=new-member`, tap the **+**, then
**Ask for access** on Arestemis; the card turns to "Asked, waiting for approval".
On the phone, hold a ring card for its page (the member's Arestemis shows
**Install the iPhone app**). Admin **Expand** shows plans; the numbered badge opens
approvals.
