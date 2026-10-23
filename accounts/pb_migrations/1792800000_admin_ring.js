/// <reference path="../pb_data/types.d.ts" />
// Approvals use an administrator's own login, never a superuser credential.
migrate((app) => {
  const users = app.findCollectionByNameOrId("users");
  users.fields.add(new BoolField({ name: "admin" }));
  users.fields.add(new JSONField({ name: "ring", maxSize: 10000 }));

  const ownFields = "@request.body.approved:isset = false && " +
    "@request.body.services:isset = false && @request.body.admin:isset = false && " +
    "@request.body.verified:isset = false";
  // Deny every other collection field, including the auth and system fields. `isset`
  // also refuses attempts to submit unchanged protected values.
  const protectedFields = [];
  for (const field of users.fields) {
    if (field.name !== "approved" && field.name !== "services") {
      protectedFields.push(field.name);
    }
  }
  protectedFields.push("passwordConfirm", "oldPassword");
  const approvalFields = protectedFields.map((name) =>
    "@request.body." + name + ":isset = false").join(" && ");

  users.createRule = ownFields;
  users.listRule = "id = @request.auth.id || @request.auth.admin = true";
  users.viewRule = users.listRule;
  users.updateRule = "(id = @request.auth.id && " + ownFields + ") || " +
    "(@request.auth.admin = true && id != @request.auth.id && " + approvalFields + ")";
  users.deleteRule = "(id = @request.auth.id && @request.auth.admin != true) || " +
    "(@request.auth.admin = true && approved = false)";
  // authRule remains verified = true && approved = true.
  app.save(users);
}, (app) => {
  const users = app.findCollectionByNameOrId("users");
  users.fields.removeByName("admin");
  users.fields.removeByName("ring");
  const editable = "@request.body.approved:isset = false && @request.body.services:isset = false";
  users.createRule = editable;
  users.listRule = "id = @request.auth.id";
  users.viewRule = "id = @request.auth.id";
  users.updateRule = "id = @request.auth.id && " + editable;
  users.deleteRule = "id = @request.auth.id";
  app.save(users);
});
