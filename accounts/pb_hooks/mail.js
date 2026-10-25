/// <reference path="../pb_data/types.d.ts" />
// What the mail hooks share (feedback.pb.js: the apps' contact & support; contact.pb.js: the website's contact form).
// PocketBase runs every handler in its own scope, so a handler loads this inside itself:
//   const mail = require(`${__hooks}/mail.js`);
// Not a hook itself: only files ending in .pb.js are loaded as hooks.

// Where messages for Patrik go: the one place to change it.
const TO = "REDACTED-EMAIL";

// The first words of a message on one line, for a subject: whole words, at most `max` characters, "…" when cut.
function summary(message, max) {
  const limit = max || 60;
  const flat = String(message).replace(/\s+/g, " ").trim();
  let result = "";
  for (const word of flat.split(" ")) {
    const longer = result ? result + " " + word : word;
    if (longer.length > limit) break;
    result = longer;
  }
  if (!result) result = flat.slice(0, limit);          // one very long word
  return result.length < flat.length ? result + "…" : result;
}

// One line of a plain mail body: "Label:    value", "–" when the value is empty.
function line(label, value) {
  return (label + ":").padEnd(10) + (value || "–");
}

// Mails a plain text to Patrik from the server's sender, with Reply-To when given. Throws when sending fails, so the
// hook can log it; the hooks call it after the record is saved, so a failure never undoes the record.
function sendToPatrik(app, subject, text, replyTo) {
  const meta = app.settings().meta;
  const message = {
    from: { address: meta.senderAddress, name: meta.senderName },
    to: [{ address: TO }],
    subject: subject,
    text: text,
  };
  if (replyTo) message.headers = { "Reply-To": replyTo };
  app.newMailClient().send(new MailerMessage(message));
}

// The record in the admin UI, for the end of a mail.
function adminLink(app, collection, id) {
  return app.settings().meta.appURL + "/_/#/collections?collection=" + collection + "&recordId=" + id;
}

module.exports = { TO, summary, line, sendToPatrik, adminLink };
