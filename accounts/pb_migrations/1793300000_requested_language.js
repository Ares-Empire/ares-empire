/// <reference path="../pb_data/types.d.ts" />
// One Ares account, run from every app (2026-10-25; docs/ACCOUNTS.md → Accounts in every app).
//
// - `requested` (the same values as `services`): the apps an account asked for and does not have yet. The account
//   sets it itself (sign-up and update); approval turns it into access (pb_hooks/accounts.pb.js).
// - `language` (`en`, `de`): the language of the emails an account gets later (approved). The account sets it.
// - Admins may change `requested` of other accounts too (the hub's approve and decline), besides `approved` and
//   `services`; every other field of another account stays out of their reach, the new `language` included.
// - A sign-up cannot choose its record id: the id is the key of an account's data in every service, so the id of a
//   deleted account must never come back to a new one.
// - Accounts waiting for approval with no services signed up on the website before this: they request `empire`.

const OWN_FIELDS = "@request.body.approved:isset = false && " +
  "@request.body.services:isset = false && @request.body.admin:isset = false && " +
  "@request.body.verified:isset = false";

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

migrate((app) => {
  const users = app.findCollectionByNameOrId("users");
  const services = users.fields.getByName("services");
  const values = [];
  for (let i = 0; i < services.values.length; i++) values.push(services.values[i]);
  users.fields.add(new SelectField({ name: "requested", maxSelect: values.length, values: values }));
  users.fields.add(new SelectField({ name: "language", maxSelect: 1, values: ["en", "de"] }));

  users.createRule = OWN_FIELDS + " && @request.body.id:isset = false";
  users.updateRule = "(id = @request.auth.id && " + OWN_FIELDS + ") || " +
    adminRule(users, ["approved", "services", "requested"]);
  app.save(users);

  for (const record of app.findRecordsByFilter("users", "approved = false && services:length = 0", "", 0, 0)) {
    record.set("requested", ["empire"]);
    app.save(record);
  }
}, (app) => {
  const users = app.findCollectionByNameOrId("users");
  users.fields.removeByName("requested");
  users.fields.removeByName("language");
  users.createRule = OWN_FIELDS;
  users.updateRule = "(id = @request.auth.id && " + OWN_FIELDS + ") || " + adminRule(users, ["approved", "services"]);
  app.save(users);
});
