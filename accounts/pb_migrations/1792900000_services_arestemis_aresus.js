/// <reference path="../pb_data/types.d.ts" />
// Two more services an account can be given (2026-10-24): the Arestemis app (flat hunting) and the Aresus app
// (the watchtower and the Aresync runs). Like every service, only a superuser or an admin sets them.
const ADDED = ["arestemis", "aresus"];

migrate((app) => {
  const users = app.findCollectionByNameOrId("users");
  const services = users.fields.getByName("services");
  services.values = services.values.concat(ADDED.filter((value) => !services.values.includes(value)));
  services.maxSelect = services.values.length;
  app.save(users);
}, (app) => {
  const users = app.findCollectionByNameOrId("users");
  const services = users.fields.getByName("services");
  services.values = services.values.filter((value) => !ADDED.includes(value));
  services.maxSelect = services.values.length;
  app.save(users);
});
