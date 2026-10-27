/// <reference path="../pb_data/types.d.ts" />
// Bank formats shared from Aresium (2026-10-27, brief 21): when Aresium does not know someone's bank, they confirm how
// the file reads, type the bank's name and tap Send. The app sends only the file's format (a `CsvLayout` from the
// engine's `shareableLayout`: separator, header names, which column means what, date and number style), never a
// payment, amount, IBAN or name. `pb_hooks/bank-formats.pb.js` checks each one again and mails it to Patrik, and
// Claude adds the bank for everyone with the next app update.
//
// - Create is open to everyone (createRule ""), like the contact form: no Ares account is needed to send. Nobody but a
//   superuser can list, view, change or delete them (null).
// - `bank`: what the person typed, one line with at least one visible character (control characters and line breaks
//   are refused). `app_version` holds only the characters of a version ("1.0 (12)"), so it cannot carry an address.
// - `layout`: at most 8 KB as stored; the hook checks its shape and that nothing in it looks like personal data.
// - At most 5 creates per hour from one address (PocketBase's rate limiter, label "bank_formats:create"). The address
//   is the sender's: Caddy's X-Forwarded-For, trusted since the first migration.
const RATE_LIMIT = { label: "bank_formats:create", audience: "", duration: 3600, maxRequests: 5 };

migrate((app) => {
  const formats = new Collection({
    type: "base",
    name: "bank_formats",
    fields: [
      {
        type: "text", name: "bank", required: true, max: 100,
        pattern: "^[^\\x00-\\x1f\\x7f]*[^\\x00-\\x20\\x7f][^\\x00-\\x1f\\x7f]*$",
      },
      { type: "json", name: "layout", required: true, maxSize: 8192 },
      { type: "text", name: "app_version", max: 40, pattern: "^[0-9A-Za-z .()+_-]*$" },
      { type: "select", name: "language", maxSelect: 1, values: ["en", "de"] },
      { type: "autodate", name: "created", onCreate: true, onUpdate: false },
    ],
    indexes: ["CREATE INDEX idx_bank_formats_created ON bank_formats (created)"],
    createRule: "",
    listRule: null,
    viewRule: null,
    updateRule: null,
    deleteRule: null,
  });
  app.save(formats);

  const settings = app.settings();
  settings.rateLimits.rules = settings.rateLimits.rules
    .filter((rule) => rule.label !== RATE_LIMIT.label)
    .concat([RATE_LIMIT]);
  app.save(settings);
}, (app) => {
  app.delete(app.findCollectionByNameOrId("bank_formats"));
  const settings = app.settings();
  settings.rateLimits.rules = settings.rateLimits.rules.filter((rule) => rule.label !== RATE_LIMIT.label);
  app.save(settings);
});
