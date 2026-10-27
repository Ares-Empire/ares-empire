// The account rules the hooks share. PocketBase runs each handler in its own scope, so a handler loads this module
// itself: `const accounts = require(`${__hooks}/lib/accounts.js`)`. Contract: docs/ACCOUNTS.md → Accounts in every app.

// How each service is named in emails. The values an account can have come from the `services` field (migrations);
// a service missing here is shown by its value.
const NAMES = {
  empire: "Ares Empire", aresium: "Aresium", arestemis: "Arestemis", aresus: "Aresus", arestoteles: "Arestoteles",
};

/** A Go string slice as a plain JS array (with filter, includes, …). */
function strings(slice) {
  const out = [];
  for (let i = 0; i < (slice ? slice.length : 0); i++) out.push(String(slice[i]));
  return out;
}

/** A multi-select field of a record as a plain JS array of strings. */
function values(record, field) {
  return strings(record.getStringSlice(field));
}

/** The values of `a` that are not in `b`, in `a`'s order. */
function without(a, b) {
  return a.filter((value) => !b.includes(value));
}

/** `a` followed by the values of `b` it lacks. */
function union(a, b) {
  return a.concat(without(b, a));
}

/** Every service an account can be given (the `services` field's values). */
function services(app) {
  return strings(app.findCollectionByNameOrId("users").fields.getByName("services").values);
}

/**
 * Brings a users record to its two rules before every save (sign-up, update, admin UI, hooks):
 * - when it becomes approved (was not, now is), it gets what it asked for: services = services ∪ requested;
 * - `requested` only holds what the account does not have yet: requested = requested − services.
 * Granting a request is therefore "put the service into `services`", in the admin UI or through the hub.
 */
function settle(record, wasApproved) {
  let granted = values(record, "services");
  let requested = values(record, "requested");
  if (record.getBool("approved") && !wasApproved) granted = union(granted, requested);
  requested = without(requested, granted);
  record.set("services", granted);
  record.set("requested", requested);
}

/** A record's language for the emails it gets: "de" or "en" (also when it never chose). */
function language(record) {
  return record.getString("language") === "de" ? "de" : "en";
}

/** "Arestemis, Aresium" (or "–" for none). */
function names(list) {
  return list.length ? list.map((value) => NAMES[value] || value).join(", ") : "–";
}

// What the account routes answer the apps, in the request's language (docs/LANGUAGES.md). PocketBase sends it as
// `message` in its error shape {status, message, data}; it starts every message with a capital and ends it with a
// period, so each sentence here already does.
const ANSWERS = {
  adminAccount: {
    en: "This is the administrator account; it cannot leave an app or be deleted here.",
    de: "Das ist das Administratorkonto. Es kann hier keine App verlassen und nicht gelöscht werden.",
  },
  unknownService: { en: "Unknown service.", de: "Unbekannter Dienst." },
};

/**
 * The language of an Accept-Language header, "de" or "en": among the tags whose primary language is de or en, the one
 * with the highest quality, the first on a tie; English when there is none. The same rule as the hub's
 * empire_language.py.
 */
function requestLanguage(header) {
  let best = "en";
  let quality = 0;
  for (const item of String(header || "").split(",")) {
    const parts = item.trim().toLowerCase().split(";");
    const tag = parts[0].trim();
    if (!/^(?:de|en)(?:-[a-z0-9]{1,8})*$/.test(tag)) continue;
    let q = 1;
    if (parts.length > 1) {
      if (parts.length !== 2 || !/^\s*q\s*=\s*(?:0(?:\.\d{0,3})?|1(?:\.0{0,3})?)\s*$/.test(parts[1])) continue;
      q = parseFloat(parts[1].split("=")[1]);
    }
    if (q > quality) {
      best = tag.split("-")[0];
      quality = q;
    }
  }
  return best;
}

/**
 * The language of a record request event `e` (onRecordCreateRequest and the like), "de" or "en", by the rule of
 * requestLanguage(). Such an event has no `e.request` in hooks; requestInfo() has the headers, lower case with "_"
 * for "-".
 */
function recordRequestLanguage(e) {
  const headers = e.requestInfo().headers || {};
  return requestLanguage(headers["accept_language"]);
}

/** A sentence of ANSWERS in the language of the request event `e`. */
function answer(e, key) {
  return ANSWERS[key][requestLanguage(e.request.header.get("Accept-Language"))];
}

module.exports = {
  NAMES, values, without, union, services, settle, language, names, requestLanguage, recordRequestLanguage, answer,
};
