/// <reference path="../pb_data/types.d.ts" />
// Deleting an account reaches every service that keeps data per account (migration 1793300100_deletions.js,
// docs/ACCOUNTS.md → Accounts in every app). The logic is in lib/deletions.js; PocketBase runs each handler in its own
// scope, so every handler loads it itself.

// The account change and its jobs commit together; only the cron calls other services.
onRecordDelete((e) => {
  e.app.runInTransaction((txApp) => {
    e.app = txApp;
    e.next();
    require(`${__hooks}/lib/deletions.js`).plan(txApp, e.record.id);
  });
}, "users");

onRecordUpdate((e) => {
  const jobs = require(`${__hooks}/lib/deletions.js`);
  const before = e.record.original();
  e.record.ignoreUnchangedFields(true);
  e.app.runInTransaction((txApp) => {
    e.app = txApp;
    const current = txApp.findRecordById("users", e.record.id);
    jobs.mergeAccess(before, current, e.record);
    const changed = jobs.accessChanged(current, e.record);
    e.record.set("access_generation", current.getInt("access_generation") + (changed ? 1 : 0));
    e.next();
    if (changed) jobs.planAccess(txApp, current, e.record);
  });
}, "users");

// Every 5 minutes: call the services of the open jobs. Run by hand: admin UI → Settings → Crons → empire-deletions.
cronAdd("empire-deletions", "*/5 * * * *", () => {
  require(`${__hooks}/lib/deletions.js`).run($app);
});
