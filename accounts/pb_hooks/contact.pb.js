/// <reference path="../pb_data/types.d.ts" />
// The contact collection (migrations 1793200000_contact.js, 1793700000_contact_app_kind.js): the hub's contact form,
// each app's own form on its website (aresium.de/contact) and Aresium's Contact & support without a login. Checks and
// email text: lib/contact.js. PocketBase runs each handler in its own scope, so every handler loads what it needs.

// Before a create is saved: text is needed unless the message asks for the app, which needs the app (400 otherwise).
onRecordCreateRequest((e) => {
  require(`${__hooks}/lib/contact.js`).refuseIncomplete(e);
  e.next();
}, "contact");

// After a create: mail it to Patrik (lib/mail.js), with Reply-To the address the visitor gave (checked by the email
// field) so he can answer from his inbox. A failed email is logged and the record stays (he still finds it in the
// admin UI); it never fails the create.
onRecordAfterCreateSuccess((e) => {
  e.next();

  const app = e.app;
  const record = e.record;
  try {
    const message = require(`${__hooks}/lib/contact.js`).email(app, record);
    require(`${__hooks}/lib/mail.js`).sendSupport(app, message.subject, message.text, message.replyTo);
  } catch (err) {
    app.logger().error("contact email failed", "contact", record.id, "error", String(err));
  }
}, "contact");
