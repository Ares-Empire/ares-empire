/// <reference path="../pb_data/types.d.ts" />
// The ring is every app an account has (Patrik, 2026-10-25; docs/EMPIRE-APP.md → Whose ring shows what): the hub
// builds it from `services`, so the saved `ring` of migration 1792800000_admin_ring.js goes, with what it held (data
// minimisation, docs/PRIVACY.md). Nothing else reads it.
//
// The admins' part of the update rule names every field of another account they may not touch, `ring` among them since
// migration 1793300000_requested_language.js; it is written again from the fields that are left, the same way.
// Down: the field comes back empty (the rings it held are gone) and the rule names it again.

const OWN_FIELDS = "@request.body.approved:isset = false && " +
  "@request.body.services:isset = false && @request.body.admin:isset = false && " +
  "@request.body.verified:isset = false";
const ADMIN_MAY_CHANGE = ["approved", "services", "requested"];

/** The admins' part of the update rule: every field of another account except `allowed` stays unset. */
function adminRule(users, allowed) {
  const untouchable = [];
  for (const field of users.fields) {
    if (!allowed.includes(field.name)) untouchable.push(field.name);
  }
  untouchable.push("passwordConfirm", "oldPassword");
  return "(@request.auth.admin = true && id != @request.auth.id && " +
    untouchable.map((name) => "@request.body." + name + ":isset = false").join(" && ") + ")";
}

function updateRule(users) {
  return "(id = @request.auth.id && " + OWN_FIELDS + ") || " + adminRule(users, ADMIN_MAY_CHANGE);
}

migrate((app) => {
  const users = app.findCollectionByNameOrId("users");
  users.fields.removeByName("ring");
  users.updateRule = updateRule(users);
  app.save(users);
}, (app) => {
  const users = app.findCollectionByNameOrId("users");
  users.fields.add(new JSONField({ name: "ring", maxSize: 10000 }));
  users.updateRule = updateRule(users);
  app.save(users);
});
