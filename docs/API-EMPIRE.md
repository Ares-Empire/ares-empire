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
  pending: number;           // admin: accounts waiting for approval (sign-ups and access requests); others: 0
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
| `GET /api/empire/approvals` | admin | `[{id, email, name, created, requested: [service], approved: bool}]`: accounts that signed up and are not approved yet, and approved accounts asking for more apps (`approved: true`) |
| `POST /api/empire/approvals/:id` `{approve: true}` / `{decline: true}` | admin | approve grants what was asked (`approved = true`, `services += requested`, `requested` empties) or decline (deletes an unapproved account; clears an approved account's `requested`). [ACCOUNTS.md → Accounts in every app](ACCOUNTS.md#accounts-in-every-app) |

Auth as Aresium's `/api/*` (`aresium/docs/API-DATA.md` → Auth): session cookie or `Authorization: Bearer <Empire token>`;
401 token rejected, 403 no access (incl. a non-admin calling an admin route), 503 the account server could not be asked.

## Language

Live lines and app-facing error sentences follow `Accept-Language`; API responses set `Content-Language: en|de`.
Among tags with primary language `de` or `en`, the highest `q` wins (first on a tie); missing, unsupported or unreadable
headers mean English. Codes, keys and enums never change. Province names/texts, the chronicle and ideas stay in their
original English. The hub forwards `Accept-Language: de|en` to both live-line sources and caches per account and
language. The English website explicitly requests `en`, even in a German browser; login/sign-up/reset pages stay
English.

## Catalog

`webauth/catalog.json` (committed; not in `data/state.json`, which the empire sync rewrites) lists, per province slug,
`users: "open" | "coming-soon"`. A province not listed is private: only admins see it. Only listed provinces can be in
a non-admin ring. Today: `{"aresium": {"users": "coming-soon"}}`.

A province's iPhone app (`app`, its URL scheme) does not depend on who may see it, so it is not in the catalog but in
`APP_SCHEMES` in `webauth/server.py` (2026-10-24: `aresium://`, `arestemis://`, `aresus://`).

## Live lines

The server asks each province for one line with the visitor's own token (cached per account and language for a minute)
and puts it in `live`. Aresium answers from `GET /api/pulse` there (this month's spending, or "Nothing imported for <month> yet").
Every other province gets Aresus's line for it (2026-10-24): one `GET /api/aresus/overview` per account and minute on
localhost (`ARESUS_OVERVIEW_URL`), "Issue: " (German: "Problem: ") in front when the province has one (e.g.
"Off on purpose · website up", "Issue: Server down since 04:53"). Accounts without the `aresus` service get no line.
