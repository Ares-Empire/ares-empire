/// <reference path="../pb_data/types.d.ts" />
// Empire accounts: who may log in, and into which services.
//
// - New sign-ups start unapproved. Only a superuser (Patrik, in the admin UI) can set
//   `approved` or `services`; the API rules below refuse both fields from normal users.
// - Logging in needs a verified email AND approval (authRule).
// - `services` lists the provinces an account may use. Each service checks it.

const SERVICES = ["empire", "aresium"];
const USER_EDITABLE = "@request.body.approved:isset = false && @request.body.services:isset = false";

migrate((app) => {
  const users = app.findCollectionByNameOrId("users");

  users.fields.add(new BoolField({ name: "approved" }));
  users.fields.add(new SelectField({ name: "services", maxSelect: SERVICES.length, values: SERVICES }));

  users.createRule = USER_EDITABLE;
  users.updateRule = "id = @request.auth.id && " + USER_EDITABLE;
  users.authRule = "verified = true && approved = true";
  app.save(users);

  const settings = app.settings();
  settings.meta.appName = "Ares Empire";
  settings.meta.appURL = "https://auth.ares-empire.de";
  settings.meta.senderName = "Ares Empire";
  settings.meta.senderAddress = "noreply@ares-empire.de";
  // Caddy on the same host appends the real client IP as the last X-Forwarded-For entry.
  settings.trustedProxy.headers = ["X-Forwarded-For"];
  settings.trustedProxy.useLeftmostIP = false;
  settings.rateLimits.enabled = true;
  app.save(settings);
}, (app) => {
  const users = app.findCollectionByNameOrId("users");
  users.fields.removeByName("approved");
  users.fields.removeByName("services");
  users.createRule = "";
  users.updateRule = "id = @request.auth.id";
  users.authRule = "";
  app.save(users);
});
