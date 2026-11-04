/// <reference path="../pb_data/types.d.ts" />
// Access changes use the same job list and cron as account deletions.
const GENERATION_RULE = " && @request.body.access_generation:isset = false";

migrate((app) => {
  const users = app.findCollectionByNameOrId("users");
  users.fields.add(new NumberField({
    name: "access_generation", min: 0, max: 9007199254740991, onlyInt: true,
  }));
  users.createRule += GENERATION_RULE;
  users.updateRule = "(" + users.updateRule + ")" + GENERATION_RULE;
  app.save(users);
  const jobs = app.findCollectionByNameOrId("deletions");
  jobs.fields.add(new SelectField({
    name: "operation", maxSelect: 1, values: ["delete", "pause", "remove_devices"],
  }));
  jobs.fields.add(new SelectField({ name: "app", maxSelect: 1, values: ["arestemis"] }));
  jobs.fields.add(new NumberField({ name: "generation", min: 0, max: 9007199254740991, onlyInt: true }));
  jobs.fields.add(new BoolField({ name: "superseded" }));
  jobs.fields.add(new DateField({ name: "next_attempt" }));
  jobs.indexes = [
    "CREATE UNIQUE INDEX idx_deletions_job ON deletions (account, service) WHERE operation = 'delete'",
    "CREATE INDEX idx_deletions_open ON deletions (service, done, next_attempt, created)",
  ];
  app.save(jobs);
  app.db().newQuery("UPDATE deletions SET operation = 'delete'").execute();
}, (app) => {
  // The previous runner only understands deletion jobs.
  app.db().newQuery("DELETE FROM deletions WHERE operation != 'delete'").execute();
  const jobs = app.findCollectionByNameOrId("deletions");
  jobs.fields.removeByName("operation");
  jobs.fields.removeByName("app");
  jobs.fields.removeByName("generation");
  jobs.fields.removeByName("superseded");
  jobs.fields.removeByName("next_attempt");
  jobs.indexes = [
    "CREATE UNIQUE INDEX idx_deletions_job ON deletions (account, service)",
    "CREATE INDEX idx_deletions_open ON deletions (done, created)",
  ];
  app.save(jobs);
  const users = app.findCollectionByNameOrId("users");
  users.fields.removeByName("access_generation");
  users.createRule = users.createRule.slice(0, -GENERATION_RULE.length);
  users.updateRule = users.updateRule.slice(1, -GENERATION_RULE.length - 1);
  app.save(users);
});
