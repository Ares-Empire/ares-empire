/// <reference path="../pb_data/types.d.ts" />
// Deleting an account reaches every service (2026-10-25; docs/ACCOUNTS.md → Accounts in every app): after a users
// record is deleted, pb_hooks/deletions.pb.js writes one job per service that keeps data per account, and a cron
// calls each open job until the service confirms. Superusers only (the API rules are null).
//
// `account` is the deleted account's id (text: the account itself is gone). `reported` (CONTRACT ADDITION) remembers
// that Patrik was mailed about a job still failing after a day, so he is mailed once.
const SERVICES = ["arestemis", "push"];

migrate((app) => {
  const deletions = new Collection({
    type: "base",
    name: "deletions",
    fields: [
      { type: "text", name: "account", required: true, min: 1, max: 64 },
      { type: "select", name: "service", required: true, maxSelect: 1, values: SERVICES },
      { type: "number", name: "attempts", min: 0, onlyInt: true },
      { type: "bool", name: "done" },
      { type: "text", name: "last_error", max: 500 },
      { type: "bool", name: "reported" },
      { type: "autodate", name: "created", onCreate: true, onUpdate: false },
      { type: "autodate", name: "updated", onCreate: true, onUpdate: true },
    ],
    indexes: [
      "CREATE UNIQUE INDEX idx_deletions_job ON deletions (account, service)",
      "CREATE INDEX idx_deletions_open ON deletions (done, created)",
    ],
    listRule: null,
    viewRule: null,
    createRule: null,
    updateRule: null,
    deleteRule: null,
  });
  app.save(deletions);
}, (app) => {
  app.delete(app.findCollectionByNameOrId("deletions"));
});
