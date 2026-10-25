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
  pending: number | null;    // admin: accounts waiting for approval (sign-ups and access requests), null when the
                             // account server could not say (the rest of the answer is complete); others: 0
}

interface Province {         // version-1 project fields, unchanged …
  slug: string; name: string; url: string; logo: string; status: string; domain: string; blurb: string;
  detail: { about: string; features: string[]; setup: string; wip: string[]; ideas: string[];
            changelog: { at: string; text: string }[] };
  // … plus:
  state: "open" | "coming-soon"; // admin: always "open"; others: from the catalog
  live: string | null;          // one line from the province, e.g. "€1,339 spent in October"; null if none
  app: string | null;           // iPhone app URL scheme if the province has one (e.g. "aresium://"); else null
}
interface ChronicleEntry { at: string; project: string | null; text: string } // version 1; project null: the empire
interface Idea { title: string; note: string }                                // version 1
```

### Hub data: always in this shape

The provinces, expansions and chronicle come from `data/state.json` on the server, which empire_sync writes and Patrik
edits by hand (EMPIRE.md → The Chronicle). The server brings it to the shape above in one place (`hub_state()` in
`webauth/server.py`) before any answer, so a hand edit can never break an app's decoding:

- Exactly the fields above, nothing else (empire_sync's `lock` and any other extra field stay on the server).
- A province without a usable `slug` (text of lowercase letters, digits and `-`, starting with a letter or digit) is
  left out, and so is a second province with a slug already seen.
- Missing or wrongly typed fields get defaults: `name` the slug with a capital first letter, `logo`
  `"brand/ares-bust.webp"` (the empire crest), every other text `""`, every list `[]`; list items that are not text
  are dropped. A `changelog` entry needs `at` and `text`, else it is left out.
- A chronicle entry needs `at` and `text` (non-empty text), else it is left out; `project` is the slug, or `null`
  when missing. An idea needs a `title`; `note` defaults to `""`.
- What was left out is logged once per request (`state.json: skipped …` in the hub's journal), so a broken hand edit
  shows up there.

## Actions

| Route | Who | Does |
|---|---|---|
| `POST /api/empire/ring` `{add: slug}` / `{remove: slug}` | everyone | changes your own ring; `add` only for catalog provinces (`open` or `coming-soon`); returns the new `EmpireData` |
| `GET /api/empire/approvals` | admin | `Approval[]` (below): accounts that signed up and are not approved yet, and approved accounts asking for more apps (`approved: true`), oldest first |
| `POST /api/empire/approvals/:id` `{approve: true}` / `{decline: true}`, optionally with `requested: [service]` | admin | approve grants the account's requests (`approved = true`, `services += requested`, they leave `requested`) or decline (deletes an unapproved account; withdraws an approved account's requests); answers `Decision` (below). [ACCOUNTS.md → Accounts in every app](ACCOUNTS.md#accounts-in-every-app) |

```ts
interface Approval {
  id: string; email: string; name: string;   // name may be ""
  created: string;                           // PocketBase's format, "2026-10-24 08:40:00.000Z"
  requested: string[];                       // service ids the account asks for and does not have
  approved: boolean;                         // false: a new sign-up; true: an approved account asking for more apps
  verified: boolean;                         // the email address is confirmed (login needs it as well as approval)
}

interface Decision {         // CONTRACT ADDITION (2026-10-25): the app needs no second call after a decision
  ok: true;
  approvals: Approval[] | null; // the list as GET /api/empire/approvals gives it now; null when the account server
                                // could not be asked again: the decision itself was made, load the list again
  pending: number | null;       // approvals.length, null together with approvals
}
```

**`requested` in the decision** (CONTRACT ADDITION, 2026-10-25): the apps the card showed when Patrik decided. With
it, the decision acts only on requests that are on the card and still asked for: approve grants those, decline
withdraws those; a request made after he looked stays waiting and comes back in `approvals`. For a sign-up (not
approved yet), approving takes the unseen requests out of `requested`, since the account server grants everything left
there on a first approval. Without `requested` the decision acts on everything the account asks for at that moment.
`requested` must be a list of texts (`null` counts as not sent), else `400`.

## Errors

Auth as Aresium's `/api/*` (`aresium/docs/API-DATA.md` → Auth): session cookie or `Authorization: Bearer <Empire token>`.
Every error answer of the hub's API has one shape (CONTRACT ADDITION, 2026-10-25):

```ts
interface ApiError { error: string; code: ErrorCode } // error: a sentence for people, in the request's language
type ErrorCode = "unauthorized" | "no_access" | "admin_only" | "bad_request" | "not_found" | "rate_limited"
               | "unavailable" | "server_error";
```

`code` is a stable English word that clients act on; it is never translated. The app decides by `code` (and shows
`error`), not by the status alone.

| Status | `code` | When |
|---|---|---|
| 401 | `unauthorized` | no token, or the token is rejected (expired, revoked by a password change, malformed) |
| 403 | `no_access` | the account is not approved or lacks the `empire` service: no access to this app |
| 403 | `admin_only` | an admin route (`/api/empire/approvals…`) called by an account that is not an admin, or the account server refused an admin's approval write |
| 400 | `bad_request` | a body that is not the route's JSON object, an unknown catalog province, a bad account id or decision |
| 413 | `bad_request` | a body over 10 KB |
| 404 | `not_found` | an unknown API route, or an account that is gone (approvals) |
| 503 | `unavailable` | the account server could not be asked or answered something unreadable, or the hub data is missing; try again in a minute |
| 500 | `server_error` | anything unexpected; the hub logs it with its traceback and still answers |

`rate_limited` (429) is reserved: the hub does not send 429 today (the account server's rate limits reach clients as
`503 unavailable`). The account server itself (sign-up, leave, delete) answers in PocketBase's own error shape
`{status, message, data}` ([ACCOUNTS.md](ACCOUNTS.md#accounts-in-every-app)).

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
`APP_SCHEMES` in `webauth/server.py` (2026-10-25: `aresium://`, `arestemis://`, `aresus://`, `arestoteles://`).

## Live lines

The server asks each province for one line with the visitor's own token (cached per account and language for a minute)
and puts it in `live`. Aresium answers from `GET /api/pulse` there (this month's spending, or "Nothing imported for <month> yet").
Every other province gets Aresus's line for it (2026-10-24): one `GET /api/aresus/overview` per account and minute on
localhost (`ARESUS_OVERVIEW_URL`), "Issue: " (German: "Problem: ") in front when the province has one (e.g.
"Off on purpose · website up", "Issue: Server down since 04:53"). An account a province does not let in gets no line
from it: Aresium and Aresus need their service and the account's id in their `EMPIRE_ALLOWED_USERS` (their owner).

## Fixtures for the apps

`python3 tools/empire_samples.py OUTDIR` writes the hub's exact answers for made-up accounts (an admin, a member with
one province, a member approved just now, the approvals list, a decision, one answer per error code), made by the
server's own handler over the committed seed with a fake account server: no network, no real data. Its checks
(`check_empire` and the others) are the contract above in code; `tools/test_empire_samples.py` and
`webauth/test_server.py` use them. Run it again when this contract or the seed changes, and copy the files into
`empire-ios`.
