/// <reference path="../pb_data/types.d.ts" />
// Bank formats shared from Aresium (migration 1793500000_bank_formats.js): the app sends a bank file's format, never
// a payment; Claude adds the bank for everyone with the next app update. The checks and the email are in
// lib/bank-formats.js; PocketBase runs each handler in its own scope, so every handler loads it itself.

// Before a create is saved: refuse a format that is not in the shape the app sends or holds anything that looks like
// personal data (a 400 with a sentence in the request's language). The app checks the same first; this is the second
// check, for an app with a bug.
onRecordCreateRequest((e) => {
  require(`${__hooks}/lib/bank-formats.js`).refuseUnsafe(e);
  e.next();
}, "bank_formats");

// After a create: mail the format to Patrik (lib/mail.js), with the command that turns it into a bank profile. A
// failed email is logged and the record stays (he still finds it in the admin UI); it never fails the create.
onRecordAfterCreateSuccess((e) => {
  e.next();

  const app = e.app;
  const record = e.record;
  try {
    const mail = require(`${__hooks}/lib/mail.js`);
    const message = require(`${__hooks}/lib/bank-formats.js`).email(app, record);
    mail.sendSupport(app, message.subject, message.text);
  } catch (err) {
    app.logger().error("bank format email failed", "bank_formats", record.id, "error", String(err));
  }
}, "bank_formats");
