/// <reference path="../../pb_data/types.d.ts" />
// The contact collection's checks and its email to Patrik (pb_hooks/contact.pb.js; migrations 1793200000_contact.js and
// 1793700000_contact_app_kind.js). Three senders write to it, all without a login:
// - an app's own contact page on the web: name, email, message, language, `app` and `kind`. Aresium's on aresium.de
//   (/contact, /kontakt), and since 2026-11-01 on the hub the Ares Empire's (www.ares-empire.de/contact, /kontakt; app
//   `empire`, also the Empire's general contact) and Arestemis's (/arestemis/contact, /arestemis/kontakt). The hub's
//   older general form sent no app or kind; a message without them is still taken ("[Website] Contact: …");
// - an iPhone app's Contact & support without a login (Aresium): builds out today end the message with a footer,
//   "— Aresium 1.0 (12) · iOS 27.0 · iPhone · Problem" (empire-ios Shared/Support/SupportMessage.swift), read here
//   as if it were `app`, `app_version`, `system` and `kind`; a later build can send those as fields instead.
// Not a hook itself: only files ending in .pb.js are loaded as hooks.

// The apps' names and the kinds as Patrik's emails say them (the same words as feedback.pb.js, plus asking for the app).
const APPS = {
  empire: "Ares Empire", aresium: "Aresium", arestemis: "Arestemis", aresus: "Aresus", arestoteles: "Arestoteles",
};
const KINDS = { access: "Get the app", question: "Question", problem: "Problem", idea: "Idea", other: "Other" };
// The footer names the kind in English (SupportKind.englishName in empire-ios).
const FOOTER_KINDS = { Problem: "problem", Idea: "idea", Question: "question", Other: "other" };

// PocketBase's own answer for a missing field, so every client reads it as it reads the field checks.
function missing(field) {
  const data = {};
  data[field] = new ValidationError("validation_required", "Cannot be blank.");
  return new BadRequestError("Failed to create record.", data);
}

/**
 * In the create request `e`: a message needs text unless it asks for the app (`kind` access), and asking for the app
 * needs the app. Throws PocketBase's 400 for the missing field (`data.message` or `data.app`); nothing is saved then.
 */
function refuseIncomplete(e) {
  const record = e.record;
  const asksForApp = record.getString("kind") === "access";
  if (asksForApp && !record.getString("app")) throw missing("app");
  if (!asksForApp && !record.getString("message")) throw missing("message");
}

/**
 * The footer an iPhone app's message ends with, read into its parts, or null: {text (the message without it), app,
 * version, system, kind}. Only Aresium sends one.
 */
function footer(message) {
  const found = /\n— (Aresium) ([^\n]*)$/.exec(message);
  if (!found) return null;
  const parts = found[2].split(" · ");
  return {
    text: message.slice(0, found.index).trim(),
    app: found[1].toLowerCase(),
    version: parts[0],
    system: parts.slice(1, -1).join(" · "),
    kind: FOOTER_KINDS[parts[parts.length - 1]] || "",
  };
}

/** The email to Patrik about a new contact record: {subject, text, replyTo}. */
function email(app, record) {
  const mail = require(`${__hooks}/lib/mail.js`);
  const german = record.getString("language") === "de";
  const address = record.getString("email");
  const old = footer(record.getString("message"));
  const text = old ? old.text : record.getString("message");
  const appKey = record.getString("app") || (old ? old.app : "");
  const kindKey = record.getString("kind") || (old ? old.kind : "");
  const version = record.getString("app_version") || (old ? old.version : "");
  const system = record.getString("system") || (old ? old.system : "");
  const appName = APPS[appKey] || "";
  const kind = KINDS[kindKey] || "";
  const asksForApp = kindKey === "access";
  const fromPhone = Boolean(old || version || system);
  const language = german ? "German" : "English";

  let first;
  if (fromPhone) first = "A message from " + (appName || "an app") + "'s Contact & support, sent without a login (" + language + ")";
  else if (asksForApp) first = "Someone asks for " + appName + " on its website (" + language + " page)";
  else if (appName) first = "A message from " + appName + "'s website (" + language + " page)";
  else first = "A message from the website's contact form (" + language + " page)";

  const lines = [first, ""];
  if (kind) lines.push(mail.line("Kind", kind));
  if (appName) lines.push(mail.line("App", appName));
  lines.push(mail.line("Name", record.getString("name")), mail.line("Email", address),
    mail.line("Language", record.getString("language")));
  if (version) lines.push(mail.line("Version", version));
  if (system) lines.push(mail.line("System", system));
  lines.push("", text || "(no message)", "", "--",
    asksForApp ? "To send the install link, reply to this email: it goes to " + address + "."
      : "Reply to this email to answer: it goes to " + address + ".",
    "In the admin UI: " + mail.adminLink(app, "contact", record.id));

  // "[Aresium] Question: <first words>", as feedback's emails; the general form keeps "[Website] Contact: …".
  const topic = kind || (german ? "Kontakt" : "Contact");
  const subject = "[" + (appName || "Website") + "] " + topic + ": " + (text ? mail.summary(text) : address);
  return { subject: subject, text: lines.join("\n"), replyTo: address };
}

module.exports = { APPS, KINDS, refuseIncomplete, footer, email };
