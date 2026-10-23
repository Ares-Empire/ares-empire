/// <reference path="../pb_data/types.d.ts" />
// Website logins keep the Empire token in a cookie; let it last 30 days like the old sessions.

migrate((app) => {
  const users = app.findCollectionByNameOrId("users");
  users.authToken.duration = 30 * 24 * 60 * 60;
  app.save(users);
}, (app) => {
  const users = app.findCollectionByNameOrId("users");
  users.authToken.duration = 7 * 24 * 60 * 60;
  app.save(users);
});
