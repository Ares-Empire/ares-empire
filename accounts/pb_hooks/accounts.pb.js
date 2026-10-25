/// <reference path="../pb_data/types.d.ts" />
// Accounts run from every app (docs/ACCOUNTS.md → Accounts in every app): the two rules of a users record, the
// emails around sign-up, access requests and approval, the route that leaves one app, and the administrator's refusal
// to leave or delete himself. The logic is in lib/accounts.js and lib/mail.js; PocketBase runs each handler in its own
// scope, so every handler loads them itself.

// Every save of a users record (sign-up, the account itself, an admin, the admin UI, a hook): approval grants what
// was requested, and `requested` drops what the account already has.
onRecordCreate((e) => {
  require(`${__hooks}/lib/accounts.js`).settle(e.record, false);
  e.next();
}, "users");

onRecordUpdate((e) => {
  require(`${__hooks}/lib/accounts.js`).settle(e.record, e.record.original().getBool("approved"));
  e.next();
}, "users");

// Someone signed up (on the website or in an app) → ask the superusers (Patrik) to approve, with the apps it asked for.
onRecordCreateRequest((e) => {
  e.next(); // saves the record; throws on validation errors, so nothing below runs then
  if (e.hasSuperuserAuth()) return; // created by hand in the admin UI

  const accounts = require(`${__hooks}/lib/accounts.js`);
  const mail = require(`${__hooks}/lib/mail.js`);
  const record = e.record;
  try {
    mail.sendToSuperusers(e.app, mail.signUp({
      email: record.email(),
      name: record.getString("name"),
      requested: accounts.names(accounts.values(record, "requested")),
      language: accounts.language(record),
      link: mail.adminLink(e.app, "users", record.id),
    }));
  } catch (err) {
    e.app.logger().error("approval request email failed", "error", String(err));
  }
}, "users");

// After an update: an approved account asked for more apps → tell the superusers; an account was approved or given more
// apps → tell the person, in its language. A failed email is logged; it never fails the update.
onRecordUpdateRequest((e) => {
  const accounts = require(`${__hooks}/lib/accounts.js`);
  const before = e.record.original();
  const was = {
    approved: before.getBool("approved"),
    services: accounts.values(before, "services"),
    requested: accounts.values(before, "requested"),
  };
  e.next();

  const mail = require(`${__hooks}/lib/mail.js`);
  const record = e.record;
  const services = accounts.values(record, "services");
  const requested = accounts.values(record, "requested");
  const asked = accounts.without(requested, was.requested);
  if (asked.length && record.getBool("approved") && !e.hasSuperuserAuth()) {
    try {
      mail.sendToSuperusers(e.app, mail.accessRequest({
        email: record.email(),
        name: record.getString("name"),
        asked: accounts.names(asked),
        requested: accounts.names(requested),
        services: accounts.names(services),
        language: accounts.language(record),
        link: mail.adminLink(e.app, "users", record.id),
      }));
    } catch (err) {
      e.app.logger().error("access request email failed", "error", String(err));
    }
  }

  const first = record.getBool("approved") && !was.approved;
  const granted = accounts.without(services, was.services);
  if (first || (record.getBool("approved") && granted.length)) {
    const apps = first ? services : granted;
    try {
      mail.sendToAccount(e.app, record.email(),
        mail.approved(accounts.language(record), first, accounts.names(apps), apps.includes("empire")));
    } catch (err) {
      e.app.logger().error("approved email failed", "error", String(err));
    }
  }
}, "users");

// POST /api/empire/leave {service} → {services, requested}: the logged-in account leaves one app (its access and
// any open request for it). The app deletes its data in that service first, where there is any.
// The administrator cannot leave (403): only an admin gives access, and an admin cannot change his own services, so
// he could not get back in.
routerAdd("POST", "/api/empire/leave", (e) => {
  const accounts = require(`${__hooks}/lib/accounts.js`);
  if (e.auth.getBool("admin")) {
    throw new ForbiddenError(accounts.answer(e, "adminAccount"));
  }
  const body = e.requestInfo().body || {};
  const service = body.service;
  if (typeof service !== "string" || !accounts.services(e.app).includes(service)) {
    throw new BadRequestError(accounts.answer(e, "unknownService"));
  }
  const record = e.app.findRecordById("users", e.auth.id);
  record.set("services", accounts.without(accounts.values(record, "services"), [service]));
  record.set("requested", accounts.without(accounts.values(record, "requested"), [service]));
  e.app.save(record);
  return e.json(200, { services: accounts.values(record, "services"), requested: accounts.values(record, "requested") });
}, $apis.requireAuth("users"));

// DELETE /api/collections/users/records/<own id> by an administrator → 403 with a sentence that says why. The delete
// rule refuses it anyway (migration 1792800000_admin_ring.js), but a rule only filters, so PocketBase would answer its
// generic 404 and the app could not tell the person why. This runs before the rule; the rule stays the protection.
routerUse((e) => {
  if (e.request.method !== "DELETE" || !e.auth || e.auth.collection().name !== "users" || !e.auth.getBool("admin")) {
    return e.next();
  }
  const target = /^\/api\/collections\/([^/]+)\/records\/([^/]+)$/.exec(e.request.url.path);
  const users = e.app.findCachedCollectionByNameOrId("users");
  if (target && target[2] === e.auth.id && (target[1] === users.name || target[1] === users.id)) {
    throw new ForbiddenError(require(`${__hooks}/lib/accounts.js`).answer(e, "adminAccount"));
  }
  return e.next();
});
