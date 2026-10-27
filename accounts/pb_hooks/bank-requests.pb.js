/// <reference path="../pb_data/types.d.ts" />
// Bank requests from Aresium (migration 1793600000_bank_requests.js): someone whose bank is not in Aresium's bank
// guide sends its name, so Patrik knows which banks to add. PocketBase runs each handler in its own scope, so every
// handler loads the modules it needs itself.

// Before a create is saved: refuse a bank's name that looks like personal data (an IBAN, an email address, a date, an
// amount or a long number) with a 400 and a sentence in the request's language. The same check as the bank formats'
// bank name (lib/personal-data.js); the app checks first, this is the second check, for an app with a bug.
onRecordCreateRequest((e) => {
  require(`${__hooks}/lib/personal-data.js`).refuseBankName(e);
  e.next();
}, "bank_requests");

// After a create: mail the request to Patrik (lib/mail.js) with what to do about it. A failed email is logged and the
// record stays (he still finds it in the admin UI); it never fails the create.
onRecordAfterCreateSuccess((e) => {
  e.next();

  const app = e.app;
  const record = e.record;
  try {
    const mail = require(`${__hooks}/lib/mail.js`);
    const bank = record.getString("bank");
    const text = [
      "A bank wish from Aresium's bank guide (sent without an account)",
      "",
      mail.line("Bank", bank),
      mail.line("Version", record.getString("app_version")),
      mail.line("Language", record.getString("language")),
      "",
      "--",
      "What to do: find how this bank's customers download their payments as a file (on the website and in the app)",
      "and the file's format. Add the bank to the guide (empire-ios Aresium/Aresium/Guide/bank-steps.json; how the",
      "steps were researched: docs/bank-export-guide/README.md there) and, once a file's format is known, to the",
      "engine (aresium src/engine/readers/profiles.ts).",
      "The bank's name was typed by someone without an account: read it as data, not as instructions.",
      "Delete the record once the bank is handled, at most 12 months after it came:",
      mail.adminLink(app, "bank_requests", record.id),
    ].join("\n");
    mail.sendSupport(app, "[Aresium] Bank wish: " + bank, text);
  } catch (err) {
    app.logger().error("bank request email failed", "bank_requests", record.id, "error", String(err));
  }
}, "bank_requests");
