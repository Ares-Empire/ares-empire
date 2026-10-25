/// <reference path="../../pb_data/types.d.ts" />
// The notifications the account server sends through the push service (Patrik, 2026-10-25; docs/PUSH.md → Who sends
// what): every admin account gets one for each new sign-up and each access request, with Approve and Decline on it
// (the Empire app's EMPIRE_REQUEST category); an account gets one when it was approved or given more apps. A member is
// never told anything about another account. Each notification carries English and German (`localized.de`); the push
// service picks per device. accounts.pb.js sends them next to the emails; a notification that fails is logged
// ("push failed") and never fails or undoes the request. Not a hook itself (only files ending in .pb.js are); a handler
// loads it with `require(`${__hooks}/lib/push.js`)`.

const APP = "de.ares-empire.empire"; // the Empire app: approvals for the admins, the ring for everyone else
const TIMEOUT = 3; // seconds: the push service runs on this host; a request is never held up for longer

const TEXTS = {
  en: {
    signUp: "New sign-up",
    request: "Access request",
    asks: (who, apps) => who + " asks for " + apps,
    created: (who) => who + " created an account",
    ready: (apps, several) => apps + (several ? " are ready" : " is ready"),
    account: "Your Ares account is ready",
    start: "Open the Empire app to start.",
    and: " and ",
  },
  de: {
    signUp: "Neue Anmeldung",
    request: "Zugangsanfrage",
    asks: (who, apps) => who + " möchte " + apps + " nutzen",
    created: (who) => who + " hat ein Konto angelegt",
    ready: (apps, several) => apps + (several ? " sind bereit" : " ist bereit"),
    account: "Dein Ares-Konto ist bereit",
    start: "Öffne die Empire-App, um loszulegen.",
    and: " und ",
  },
};

/** The apps by their names (the emails' table, NAMES): "Arestemis", "Arestemis and Aresium", "A, B and C". */
function spoken(services, language) {
  const NAMES = require(`${__hooks}/lib/accounts.js`).NAMES;
  const names = services.map((value) => NAMES[value] || value);
  if (names.length < 2) return names.join("");
  return names.slice(0, -1).join(", ") + TEXTS[language].and + names[names.length - 1];
}

/** {title, body, localized: {de}} from `text(language)` → {title, body}. */
function bilingual(text) {
  const en = text("en");
  return { title: en.title, body: en.body, localized: { de: text("de") } };
}

/**
 * To the admins: an account waits for them, a new sign-up (`signUp`) or an approved account asking for more apps.
 * account = {id, name, email, requested}; `requested` is everything it asks for now. The notification replaces the
 * account's earlier one (collapse_id), so it names all of them, and its url carries them for Approve and Decline (the
 * decision's `requested`, docs/API-EMPIRE.md).
 */
function approvalRequest(account, signUp) {
  const who = account.name || account.email;
  const apps = account.requested;
  return Object.assign(bilingual((language) => ({
    title: signUp ? TEXTS[language].signUp : TEXTS[language].request,
    body: apps.length ? TEXTS[language].asks(who, spoken(apps, language)) : TEXTS[language].created(who),
  })), {
    category: "EMPIRE_REQUEST",
    url: "empire://approvals/" + account.id + "?apps=" + apps.join(","),
    thread: "approvals",
    collapse_id: "request-" + account.id,
    sound: true,
  });
}

/** To the account `id`: approved for the first time (`apps` = everything it has now) or given more apps (the new ones). */
function ready(id, apps) {
  return Object.assign(bilingual((language) => ({
    title: apps.length ? TEXTS[language].ready(spoken(apps, language), apps.length > 1) : TEXTS[language].account,
    body: TEXTS[language].start,
  })), { url: "empire://ring", thread: "access", collapse_id: "ready-" + id });
}

/** POST <push service>/send for one account; true when the push service took it. Never throws. */
function send(app, to, message) {
  try {
    // The push service's address is kept with the other local services (lib/deletions.js; PUSH_INTERNAL_URL).
    const base = require(`${__hooks}/lib/deletions.js`).base("push");
    const res = $http.send({
      method: "POST",
      url: base + "/send",
      body: JSON.stringify(Object.assign({ app: APP, to: { user: to } }, message)),
      headers: { "Content-Type": "application/json" },
      timeout: TIMEOUT,
    });
    if (res.statusCode >= 200 && res.statusCode < 300) return true;
    app.logger().error("push failed", "thread", message.thread, "to", to, "status", res.statusCode);
  } catch (err) {
    app.logger().error("push failed", "thread", message.thread, "to", to, "error", String(err).slice(0, 300));
  }
  return false;
}

/** Sends `message` to every admin account (users with admin = true). Never throws. */
function toAdmins(app, message) {
  try {
    for (const admin of app.findRecordsByFilter("users", "admin = true", "", 0, 0)) send(app, admin.id, message);
  } catch (err) {
    app.logger().error("push failed", "thread", message.thread, "error", String(err).slice(0, 300));
  }
}

/** Sends `message` to the account `id`. Never throws. */
function toAccount(app, id, message) {
  send(app, id, message);
}

module.exports = { APP, approvalRequest, ready, toAdmins, toAccount };
