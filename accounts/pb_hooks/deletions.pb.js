/// <reference path="../pb_data/types.d.ts" />
// Deleting an account reaches every service that keeps data per account (migration 1793200100_deletions.js,
// docs/ACCOUNTS.md → Accounts in every app). The logic is in lib/deletions.js; PocketBase runs each handler in its own
// scope, so every handler loads it itself.

// After an account is deleted (by itself, by an admin declining it, in the admin UI): one job per service.
// After the deletion, never before: a job must never delete the data of an account that still exists.
onRecordAfterDeleteSuccess((e) => {
  e.next();
  require(`${__hooks}/lib/deletions.js`).plan(e.app, e.record.id);
}, "users");

// Every 5 minutes: call the services of the open jobs. Run by hand: admin UI → Settings → Crons → empire-deletions.
cronAdd("empire-deletions", "*/5 * * * *", () => {
  require(`${__hooks}/lib/deletions.js`).run($app);
});
