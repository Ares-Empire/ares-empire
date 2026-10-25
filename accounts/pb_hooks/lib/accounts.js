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

module.exports = { NAMES, values, without, union, services, settle, language, names };
