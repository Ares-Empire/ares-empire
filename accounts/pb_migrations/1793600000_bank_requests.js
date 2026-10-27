/// <reference path="../pb_data/types.d.ts" />
// Bank requests from Aresium (2026-10-27, brief 26): in Aresium's bank guide, someone whose bank is not listed sends
// its name to Patrik in two taps, so he knows which banks to add. Only the name the person typed, the app's version
// and language; no account, no file, no payment. `pb_hooks/bank-requests.pb.js` refuses a name that looks like personal
// data and mails each request to Patrik.
//
// - Create is open to everyone (createRule ""), like the bank formats: no Ares account is needed to send. Nobody but a
//   superuser can list, view, change or delete them (null).
// - `bank`: one line with at least one visible character (control characters and line breaks are refused), the same
//   as bank_formats. `app_version` holds only the characters of a version ("1.0 (12)"), so it cannot carry an address.
//   `language` may be left out.
// - At most 5 creates per hour from one address (PocketBase's rate limiter, label "bank_requests:create"). The address
//   is the sender's: Caddy's X-Forwarded-For, trusted since the first migration.
const RATE_LIMIT = { label: "bank_requests:create", audience: "", duration: 3600, maxRequests: 5 };

migrate((app) => {
  const requests = new Collection({
    type: "base",
    name: "bank_requests",
    fields: [
      {
        type: "text", name: "bank", required: true, max: 100,
        pattern: "^[^\\x00-\\x1f\\x7f]*[^\\x00-\\x20\\x7f][^\\x00-\\x1f\\x7f]*$",
      },
      { type: "text", name: "app_version", max: 40, pattern: "^[0-9A-Za-z .()+_-]*$" },
      { type: "select", name: "language", maxSelect: 1, values: ["en", "de"] },
      { type: "autodate", name: "created", onCreate: true, onUpdate: false },
    ],
    indexes: ["CREATE INDEX idx_bank_requests_created ON bank_requests (created)"],
    createRule: "",
    listRule: null,
    viewRule: null,
    updateRule: null,
    deleteRule: null,
  });
  app.save(requests);

  const settings = app.settings();
  settings.rateLimits.rules = settings.rateLimits.rules
    .filter((rule) => rule.label !== RATE_LIMIT.label)
    .concat([RATE_LIMIT]);
  app.save(settings);
}, (app) => {
  app.delete(app.findCollectionByNameOrId("bank_requests"));
  const settings = app.settings();
  settings.rateLimits.rules = settings.rateLimits.rules.filter((rule) => rule.label !== RATE_LIMIT.label);
  app.save(settings);
});
