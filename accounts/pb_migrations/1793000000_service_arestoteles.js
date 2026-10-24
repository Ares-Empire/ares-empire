/// <reference path="../pb_data/types.d.ts" />
// One more service an account can be given (2026-10-24): the Arestoteles app (Patrik's Weltbild vault on the phone).
// Like every service, only a superuser or an admin sets it.
const ADDED = ["arestoteles"];

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
