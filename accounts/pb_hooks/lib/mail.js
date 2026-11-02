/// <reference path="../../pb_data/types.d.ts" />
// Everything the mail hooks share: who gets which email, how it is sent, and the texts of the account emails.
// PocketBase runs every handler in its own scope, so a handler loads this inside itself:
//   const mail = require(`${__hooks}/lib/mail.js`);
// Not a hook itself: only files ending in .pb.js are loaded as hooks.
//
// Patrik is reached two ways, on purpose:
// - SUPPORT_TO, for what people write to him: the apps' contact & support (feedback.pb.js) and the contact forms on
//   the websites (contact.pb.js, lib/contact.js). Plain text, Reply-To the writer: sendSupport().
// - superusers(), for account administration: sign-ups, access requests, a stuck deletion (accounts.pb.js,
//   lib/deletions.js). Every superuser's address except placeholders (example.com): whoever can approve in the admin
//   UI. sendToSuperusers().
// A person's own email (approved, in the account's `language`) goes to the account's address: sendToAccount().
// PocketBase's own verification and password-reset emails are templates (migration 1793300200_emails_de_en.js).

// The installer passes only the email from the machine-local owner file.
const SUPPORT_TO = $os.getenv("ARES_OWNER_EMAIL");
if (!SUPPORT_TO || !SUPPORT_TO.trim()) {
  throw new Error("ARES_OWNER_EMAIL is missing; run deploy/install-accounts.sh with a valid owner file");
}

const LANGUAGES = { en: "English", de: "German" };
const HUB = "https://www.ares-empire.de/login";

// ── Sending ──────────────────────────────────────────────────────────────────

function sender(app) {
  const meta = app.settings().meta;
  return { address: meta.senderAddress, name: meta.senderName };
}

// Mails a plain text to SUPPORT_TO from the server's sender, with Reply-To when given. Throws when sending fails, so
// the hook can log it; the hooks call it after the record is saved, so a failure never undoes the record.
function sendSupport(app, subject, text, replyTo) {
  const message = { from: sender(app), to: [{ address: SUPPORT_TO }], subject: subject, text: text };
  if (replyTo) message.headers = { "Reply-To": replyTo };
  app.newMailClient().send(new MailerMessage(message));
}

// The superusers' addresses, except placeholders (example.com).
function superusers(app) {
  const to = [];
  for (const record of app.findAllRecords("_superusers")) {
    const address = String(record.email() || "");
    if (address && !address.endsWith("@example.com")) to.push({ address: address });
  }
  return to;
}

function sendHtml(app, to, message) {
  app.newMailClient().send(new MailerMessage({ from: sender(app), to: to, subject: message.subject, html: message.html }));
}

// Mails `{subject, html}` to the superusers; false when there is none to send to. Throws when sending fails.
function sendToSuperusers(app, message) {
  const to = superusers(app);
  if (!to.length) return false;
  sendHtml(app, to, message);
  return true;
}

// Mails `{subject, html}` to one account's address. Throws when sending fails.
function sendToAccount(app, address, message) {
  sendHtml(app, [{ address: address }], message);
}

// ── Pieces of a message ──────────────────────────────────────────────────────

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

// The record in the admin UI, for the end of a mail.
function adminLink(app, collection, id) {
  return app.settings().meta.appURL + "/_/#/collections?collection=" + collection + "&recordId=" + id;
}

function escape(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" })[c]);
}

function who(account) {
  return "<b>" + escape(account.email) + "</b>" + (account.name ? " (" + escape(account.name) + ")" : "");
}

// ── The account emails ───────────────────────────────────────────────────────

// To the superusers: someone created an account. account = {email, name, requested: "Arestemis" or "–", language, link}.
function signUp(account) {
  return {
    subject: "New Ares account: " + account.email + (account.requested !== "–" ? " asks for " + account.requested : ""),
    html: "<p>" + who(account) + " created an Ares account.</p>" +
      "<p>Asks for: <b>" + escape(account.requested) + "</b><br>Language: " + LANGUAGES[account.language] + "</p>" +
      "<p>To let them in, open <a href=\"" + escape(account.link) + "\">their account</a> and switch on " +
      "<b>approved</b>: the account then gets the apps it asked for (<b>requested</b>) and an email in its language. " +
      "Approvals in the Empire app do the same.</p>" +
      "<p>They can log in once they have also confirmed their email address. To decline, delete the account there.</p>",
  };
}

// To the superusers: an approved account asks for more apps. account = {email, name, asked, requested, services,
// language, link}.
function accessRequest(account) {
  return {
    subject: "Ares access request: " + account.email + " asks for " + account.asked,
    html: "<p>" + who(account) + " asks for access to <b>" + escape(account.asked) + "</b>.</p>" +
      "<p>Has: " + escape(account.services) + "<br>Asks for (all open): " + escape(account.requested) +
      "<br>Language: " + LANGUAGES[account.language] + "</p>" +
      "<p>To grant it, open <a href=\"" + escape(account.link) + "\">their account</a> and add the apps to " +
      "<b>services</b> (they leave <b>requested</b> by themselves, and the account gets an email). Approvals in the " +
      "Empire app do the same. To decline, remove them from <b>requested</b>.</p>",
  };
}

const APPROVED = {
  en: {
    first: "Your Ares account is ready",
    more: (apps) => "You now have access to " + apps,
    hello: "Hello,",
    firstLine: (apps) => "your Ares account was approved." + (apps ? " You can now use: <b>" + apps + "</b>." : ""),
    moreLine: (apps) => "your Ares account now also has access to <b>" + apps + "</b>.",
    login: "Open the app and log in with this email address and your password.",
    hub: "The Ares Empire hub on the web:",
  },
  de: {
    first: "Dein Ares-Konto ist bereit",
    more: (apps) => "Du hast jetzt Zugang zu " + apps,
    hello: "Hallo,",
    firstLine: (apps) => "dein Ares-Konto wurde freigegeben." + (apps ? " Du kannst jetzt nutzen: <b>" + apps + "</b>." : ""),
    moreLine: (apps) => "dein Ares-Konto hat jetzt auch Zugang zu <b>" + apps + "</b>.",
    login: "Öffne die App und melde dich mit dieser E-Mail-Adresse und deinem Passwort an.",
    hub: "Der Ares-Empire-Hub im Web:",
  },
};

// To the person, in its language: approved for the first time (`first`), or given more apps. `apps` are the services
// it can use now (first time) or the new ones, as names ("Arestemis, Ares Empire"); `hub` adds the website's address
// (when the hub is among them).
function approved(language, first, apps, hub) {
  const t = APPROVED[language] || APPROVED.en;
  const shown = apps === "–" ? "" : escape(apps);
  return {
    subject: first ? t.first : t.more(apps),
    html: "<p>" + t.hello + "</p>" +
      "<p>" + (first ? t.firstLine(shown) : t.moreLine(shown)) + "</p>" +
      "<p>" + t.login + "</p>" +
      (hub ? "<p>" + t.hub + " <a href=\"" + HUB + "\">www.ares-empire.de</a></p>" : "") +
      "<p>Ares Empire</p>",
  };
}

// To the superusers: deleting a deleted account's data in a service keeps failing. job = {account, service, since,
// attempts, error, link}.
function deletionStuck(job) {
  return {
    subject: "Ares account deletion stuck: " + job.service,
    html: "<p>Deleting the data of a deleted account in <b>" + escape(job.service) + "</b> keeps failing since " +
      escape(job.since) + " (" + job.attempts + " attempts).</p>" +
      "<p>Account id: " + escape(job.account) + "<br>Last error: " + escape(job.error || "–") + "</p>" +
      "<p>The account server keeps trying every 5 minutes. To stop it (after deleting the data by hand), switch on " +
      "<b>done</b> in <a href=\"" + escape(job.link) + "\">the job</a>.</p>",
  };
}

module.exports = {
  SUPPORT_TO, sendSupport, superusers, sendToSuperusers, sendToAccount,
  summary, line, adminLink,
  signUp, accessRequest, approved, deletionStuck,
};
