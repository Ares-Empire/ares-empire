# Phone previews

Start a local preview from the worktree:

```sh
cd web && python3 -m http.server 8765
```

- http://localhost:8765/?skipIntro — admin sample.
- http://localhost:8765/?as=user&skipIntro — member sample.

At widths up to 620 px it mounts `window.EmpireMobile`; wider windows keep the
desktop scene. Omit `skipIntro` to play the slam once per session (unless reduced
motion is enabled).

Sample mode works only on `localhost` or `127.0.0.1`. It fetches the selected JSON
fixture; sample actions update memory and reloading resets them. Other hosts,
including ares-empire.de, always use `/api/empire` with session cookies and ignore
`as` and `skipIntro`. The phone requires version 2 and shows a retry/login state on
failure. The desktop keeps its seed fallback and rendering. `file://` is unsupported.

The JSON fixtures copy the seed’s provinces and ideas, with the version-2 account
fields. The two Aresium news entries come from the charter’s October 23 updates.
Accounts in the approvals preview are fictional `example.com` accounts.

The member starts with Aresium in the ring (`coming-soon`) and an empty catalog.
To preview adding: open Aresium, scroll to **Remove from my ring**, then tap the
**+** card. Add returns it to the ring and restores its news. The Add sheet otherwise
shows an empty state. Admin **Expand** shows plans; the numbered badge opens approvals.

