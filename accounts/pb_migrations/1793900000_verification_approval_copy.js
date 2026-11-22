/// <reference path="../pb_data/types.d.ts" />
// Refresh the approval sentences in templates already saved by 1793300200_emails_de_en.js.
// Keep any other template edits. Rolling back does not restore the personal name.
migrate((app) => {
  const users = app.findCollectionByNameOrId("users");
  const body = users.verificationTemplate.body;
  const updated = body
    .replace(/<p>Then [^<\r\n]+ approves the account, and you get an email/, "<p>Then your account is approved, and you get an email")
    .replace(/<p>Danach gibt [^<\r\n]+ das Konto frei, und du bekommst eine E-Mail/, "<p>Danach wird dein Konto freigegeben, und du bekommst eine E-Mail");
  if (updated !== body) {
    users.verificationTemplate.body = updated;
    app.save(users);
  }
}, () => {});
