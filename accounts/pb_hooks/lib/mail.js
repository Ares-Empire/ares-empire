// The emails the account hooks write: to Patrik (sign-ups, access requests, a stuck deletion; English, like the
// support emails) and to a person once approved (in the account's `language`). PocketBase's own verification and
// password-reset emails are templates (migration 1793200200_emails_de_en.js). Loaded by the handlers with
// `require(`${__hooks}/lib/mail.js`)`.

const LANGUAGES = { en: "English", de: "German" };
const HUB = "https://www.ares-empire.de/login";

function escape(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" })[c]);
}

/** Patrik: every superuser's address except placeholders (example.com). */
function owners(app) {
  const to = [];
  for (const record of app.findAllRecords("_superusers")) {
    const address = String(record.email() || "");
    if (address && !address.endsWith("@example.com")) to.push({ address: address });
  }
  return to;
}

/** Sends `{subject, html}` from the server's sender; false when there is nobody to send it to. Throws on failure. */
function send(app, to, message) {
  if (!to.length) return false;
  const meta = app.settings().meta;
  app.newMailClient().send(new MailerMessage({
    from: { address: meta.senderAddress, name: meta.senderName },
    to: to,
    subject: message.subject,
    html: message.html,
  }));
  return true;
}

/** The account in the admin UI (approve, decline, grant there). */
function accountLink(app, id) {
  return app.settings().meta.appURL + "/_/#/collections?collection=users&recordId=" + encodeURIComponent(id);
}

function who(account) {
  return "<b>" + escape(account.email) + "</b>" + (account.name ? " (" + escape(account.name) + ")" : "");
}

/** To Patrik: someone created an account. account = {email, name, requested: "Arestemis" or "–", language, link}. */
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

/** To Patrik: an approved account asks for more apps. account = {email, name, asked, requested, services, language, link}. */
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

/**
 * To the person, in its language: approved for the first time (`first`), or given more apps. `apps` are the
 * services it can use now (first time) or the new ones, as names ("Arestemis, Ares Empire"); `hub` adds the
 * website's address (when the hub is among them).
 */
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

/** To Patrik: deleting a deleted account's data in a service keeps failing. job = {account, service, since, attempts, error, link}. */
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

module.exports = { owners, send, accountLink, signUp, accessRequest, approved, deletionStuck };
