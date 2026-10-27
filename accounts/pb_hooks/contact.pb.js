/// <reference path="../pb_data/types.d.ts" />
// The website's contact form, and Aresium's Contact & support without a login (migration 1793200000_contact.js):
// every new contact record is mailed to Patrik
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
    // An app that works without an account (Aresium) sends its Contact & support form here too and ends the message
    // with "— Aresium 1.0 (12) · iOS 27.0 · iPhone · Problem" (empire-ios Shared/Support/SupportMessage.swift).
    const fromApp = /\n— (Aresium) [^\n]*$/.exec(message);
    const source = fromApp ? fromApp[1] : null;

    const text = [
      source ? "A message from " + source + "'s Contact & support, sent without a login (" + (german ? "German" : "English") + ")"
        : "A message from the website's contact form (" + (german ? "German" : "English") + " page)",
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

    const said = fromApp ? message.slice(0, fromApp.index) : message; // the subject sums up the message, not the footer
    mail.sendSupport(app, "[" + (source || "Website") + "] " + (german ? "Kontakt" : "Contact") + ": " + mail.summary(said),
      text, email);
  } catch (err) {
    app.logger().error("contact email failed", "contact", record.id, "error", String(err));
  }
}, "contact");
