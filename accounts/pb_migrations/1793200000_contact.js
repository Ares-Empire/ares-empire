/// <reference path="../pb_data/types.d.ts" />
// The website's contact form (2026-10-25, brief E7): anyone can write to Patrik from www.ares-empire.de/kontakt or
// /contact, without an account; the imprint names it as the second quick way to reach him. `pb_hooks/contact.pb.js`
// mails each message to him, and he reads them all in the admin UI.
//
// - Create is open to everyone (createRule ""). Nobody but a superuser can list, view, change or delete them (null).
// - `website` is a honeypot: the form hides it from people, so only a bot fills it, and any text in it is refused.
//   (A text field's max 0 means "the default limit", so "nothing allowed" is the pattern ^$.)
// - At most 5 creates per hour from one address (PocketBase's rate limiter, label "contact:create"). The address is
//   the visitor's: Caddy's X-Forwarded-For, trusted since the first migration.
const RATE_LIMIT = { label: "contact:create", audience: "", duration: 3600, maxRequests: 5 };

migrate((app) => {
  const contact = new Collection({
    type: "base",
    name: "contact",
    fields: [
      { type: "text", name: "name", max: 100 },
      { type: "email", name: "email", required: true },
      // `pattern`: at least one character that is not a space, so a message of blanks is refused too.
      { type: "text", name: "message", required: true, min: 1, max: 5000, pattern: "\\S" },
      { type: "select", name: "language", maxSelect: 1, values: ["en", "de"] },
      { type: "text", name: "website", pattern: "^$" },
      { type: "autodate", name: "created", onCreate: true, onUpdate: false },
    ],
    indexes: ["CREATE INDEX idx_contact_created ON contact (created)"],
    createRule: "",
    listRule: null,
    viewRule: null,
    updateRule: null,
    deleteRule: null,
  });
  app.save(contact);

  const settings = app.settings();
  settings.rateLimits.rules = settings.rateLimits.rules
    .filter((rule) => rule.label !== RATE_LIMIT.label)
    .concat([RATE_LIMIT]);
  app.save(settings);
}, (app) => {
  app.delete(app.findCollectionByNameOrId("contact"));
  const settings = app.settings();
  settings.rateLimits.rules = settings.rateLimits.rules.filter((rule) => rule.label !== RATE_LIMIT.label);
  app.save(settings);
});
