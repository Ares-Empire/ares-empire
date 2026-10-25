/// <reference path="../pb_data/types.d.ts" />
// Contact & support from the apps (2026-10-24): a signed-in account sends a message (a problem, an idea, a question),
// `pb_hooks/feedback.pb.js` mails it to Patrik, and he reads them all in the admin UI.
//
// - Only a verified, approved account may create one, and only as itself. Nobody but a superuser can list, view,
//   change or delete them (the API rules below are null = superusers only).
// - A record goes with its account (cascade delete).
// - At most 10 creates per hour from one client (PocketBase's rate limiter, label "feedback:create").
const APPS = ["empire", "aresium", "arestemis", "aresus", "arestoteles"];
const KINDS = ["problem", "idea", "question", "other"];
const RATE_LIMIT = { label: "feedback:create", audience: "", duration: 3600, maxRequests: 10 };

migrate((app) => {
  const users = app.findCollectionByNameOrId("users");
  const feedback = new Collection({
    type: "base",
    name: "feedback",
    fields: [
      { type: "relation", name: "user", required: true, collectionId: users.id, cascadeDelete: true, maxSelect: 1 },
      { type: "select", name: "app", required: true, maxSelect: 1, values: APPS },
      { type: "select", name: "kind", required: true, maxSelect: 1, values: KINDS },
      // `pattern`: at least one character that is not a space, so a message of blanks is refused too.
      { type: "text", name: "message", required: true, min: 1, max: 5000, pattern: "\\S" },
      { type: "text", name: "app_version", max: 40 },
      { type: "text", name: "system", max: 80 },
      { type: "select", name: "language", maxSelect: 1, values: ["en", "de"] },
      { type: "autodate", name: "created", onCreate: true, onUpdate: false },
    ],
    indexes: ["CREATE INDEX idx_feedback_created ON feedback (created)"],
    createRule: "@request.auth.collectionName = 'users' && @request.auth.verified = true && " +
      "@request.auth.approved = true && @request.body.user = @request.auth.id",
    listRule: null,
    viewRule: null,
    updateRule: null,
    deleteRule: null,
  });
  app.save(feedback);

  const settings = app.settings();
  settings.rateLimits.rules = settings.rateLimits.rules
    .filter((rule) => rule.label !== RATE_LIMIT.label)
    .concat([RATE_LIMIT]);
  app.save(settings);
}, (app) => {
  app.delete(app.findCollectionByNameOrId("feedback"));
  const settings = app.settings();
  settings.rateLimits.rules = settings.rateLimits.rules.filter((rule) => rule.label !== RATE_LIMIT.label);
  app.save(settings);
});
