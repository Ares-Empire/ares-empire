# `GET /api/empire`: the hub data, per account (version 2)

**Status:** contract agreed 2026-10-24 ([EMPIRE-APP.md](EMPIRE-APP.md)); the mobile hub is built against it first,
with sample data, then the server. Clients: the hub website (desktop and mobile) and the Empire iPhone app.

Version 1 sent the same `projects` / `ideas` / `chronicle` to everyone. Version 2 answers **per account**: the server
decides what this account sees; clients only display it. The three version-1 fields keep their names and shapes, so
the desktop hub keeps working; everything new is added.

```ts
interface EmpireData {
  version: 2;
  me: { id: string; name: string; admin: boolean };
  projects: Province[];      // the ring as THIS account sees it (admin: every province; others: own ring ∩ catalog)
  addable: Province[];       // others: catalog provinces not yet in their ring (the "+" list); admin: []
  chronicle: ChronicleEntry[]; // admin: everything; others: entries tagged with a province in their ring ("what's new")
  ideas: Idea[];             // admin only (expansions); others: []
  pending: number;           // admin: accounts waiting for approval; others: 0
}

interface Province {         // version-1 project fields, unchanged …
  slug: string; name: string; url: string; logo: string; status: string; domain: string; blurb: string;
  detail: { about: string; features: string[]; setup: string; wip: string[]; ideas: string[]; changelog: unknown[] };
  // … plus:
  state: "open" | "coming-soon"; // admin: always "open"; others: from the catalog
  live: string | null;          // one line from the province, e.g. "€1,339 spent in October"; null if none
  app: string | null;           // iPhone app URL scheme if the province has one (e.g. "aresium://"); else null
}
// ChronicleEntry and Idea: unchanged from version 1 (see web/app/empire-data.js).
```

## Actions

| Route | Who | Does |
|---|---|---|
| `POST /api/empire/ring` `{add: slug}` / `{remove: slug}` | everyone | changes your own ring; `add` only for catalog provinces (`open` or `coming-soon`); returns the new `EmpireData` |
| `GET /api/empire/approvals` | admin | `[{id, email, name, created}]`: accounts that signed up and are not approved yet |
| `POST /api/empire/approvals/:id` `{approve: true}` / `{decline: true}` | admin | approve (sets `approved`, and `services: ["empire"]`) or decline (deletes the unapproved account) |

Auth as Aresium's `/api/*` (`aresium/docs/API-DATA.md` → Auth): session cookie or `Authorization: Bearer <Empire token>`;
401 token rejected, 403 no access (incl. a non-admin calling an admin route), 503 the account server could not be asked.

## Catalog

Each province in the empire data carries `users: "open" | "coming-soon" | "private"` (default `private`). Only `open`
and `coming-soon` provinces can be in a non-admin ring. Today: `aresium: "coming-soon"`, everything else private.
