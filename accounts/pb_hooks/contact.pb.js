/// <reference path="../pb_data/types.d.ts" />
// The website's contact form (migration 1793200000_contact.js): every new contact record is mailed to Patrik
// (lib/mail.js), with Reply-To the address the visitor gave (checked by the email field) so he can answer from his inbox.
// A failed email is logged and the record stays (he still finds it in the admin UI); it never fails the create.

onRecordAfterCreateSuccess((e) => {
  e.next();

  const app = e.app;
  const record = e.record;
  try {
    const mail = require(`${__hooks}/lib/mail.js`);
    const german = record.getString("language") === "de";
    const email = record.getString("email");
    const message = record.getString("message");

    const text = [
      "A message from the website's contact form (" + (german ? "German" : "English") + " page)",
      "",
      mail.line("Name", record.getString("name")),
      mail.line("Email", email),
      mail.line("Language", record.getString("language")),
      "",
      message,
      "",
      "--",
      "Reply to this email to answer: it goes to " + email + ".",
      "In the admin UI: " + mail.adminLink(app, "contact", record.id),
    ].join("\n");

    mail.sendSupport(app, "[Website] " + (german ? "Kontakt" : "Contact") + ": " + mail.summary(message), text, email);
  } catch (err) {
    app.logger().error("contact email failed", "contact", record.id, "error", String(err));
  }
}, "contact");
