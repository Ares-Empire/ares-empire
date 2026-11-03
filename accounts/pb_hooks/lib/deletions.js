// Deleting an account reaches every service that keeps data per account (docs/ACCOUNTS.md → Accounts in every app).
// `plan` and `planAccess` write jobs into `deletions`; every 5 minutes `run` calls each open job on localhost.
// A job still failing after a day is mailed to Patrik once.
// Loaded by the handlers with `require(`${__hooks}/lib/deletions.js`)`.

// The services with per-account data, where they listen on this host, and their names in emails. An environment
// variable may point a service elsewhere (the account rule tests use a fake service); the server uses the defaults.
const SERVICES = {
  arestemis: { name: "Arestemis", env: "ARESTEMIS_INTERNAL_URL", url: "http://127.0.0.1:8097" },
  push: { name: "the push service", env: "PUSH_INTERNAL_URL", url: "http://127.0.0.1:8096" },
};
const ALERT_AFTER = 24 * 60 * 60; // seconds after the job was created
const TIMEOUT = 10; // seconds per call
const BATCH = 200; // due jobs per service per run
const RETRY_SECONDS = 5 * 60;

/** PocketBase stores dates with a space between the date and time. */
function timestamp(milliseconds) {
  return new Date(milliseconds).toISOString().replace("T", " ");
}

/** Where a service listens on this host (also the push service's /send, lib/push.js). */
function base(service) {
  const entry = SERVICES[service];
  return ($os.getenv(entry.env) || entry.url).replace(/\/+$/, "");
}

/** Writes a job after the account change succeeds. */
function saveJob(app, account, service, operation, scope, generation) {
  const collection = app.findCollectionByNameOrId("deletions");
  const job = new Record(collection);
  job.set("account", account);
  job.set("service", service);
  job.set("operation", operation);
  job.set("app", scope || "");
  job.set("generation", generation || 0);
  job.set("attempts", 0);
  job.set("done", false);
  app.save(job);
}

/** Completes old access jobs in the same transaction as the new account state. */
function supersede(app, account) {
  const filter = "account = {:account} && done = false && operation != 'delete'";
  const jobs = app.findRecordsByFilter("deletions", filter, "", 0, 0, { account: account });
  for (const job of jobs) {
    job.set("done", true);
    job.set("superseded", true);
    app.save(job);
  }
  return jobs;
}

/** One open job per service for the deleted account `account` (its id). */
function plan(app, account) {
  supersede(app, account);
  for (const service of Object.keys(SERVICES)) {
    saveJob(app, account, service, "delete");
  }
}

function servicesKey(record) {
  const accounts = require(`${__hooks}/lib/accounts.js`);
  return accounts.values(record, "services").sort().join(",");
}

function accessChanged(before, record) {
  return before.getBool("approved") !== record.getBool("approved") ||
    servicesKey(before) !== servicesKey(record);
}

/** Untouched access fields use the current database state when saving an older snapshot. */
function mergeAccess(before, current, record) {
  const accounts = require(`${__hooks}/lib/accounts.js`);
  if (before.getBool("approved") === record.getBool("approved")) {
    record.set("approved", current.getBool("approved"));
  }
  if (servicesKey(before) === servicesKey(record)) {
    record.set("services", accounts.values(current, "services"));
  }
}

function planAccess(app, before, record) {
  if (!accessChanged(before, record)) return;
  const pending = supersede(app, record.id);
  const accounts = require(`${__hooks}/lib/accounts.js`);
  const hadArestemis = accounts.values(before, "services").includes("arestemis");
  const hasArestemis = accounts.values(record, "services").includes("arestemis");
  const deniedApproval = !record.getBool("approved");
  const lostApproval = before.getBool("approved") && deniedApproval;
  const deniedArestemis = hadArestemis && !hasArestemis;
  if (!deniedApproval && hasArestemis) return;
  if (!lostApproval && !deniedArestemis && !pending.length) return;
  const generation = record.getInt("access_generation");
  saveJob(app, record.id, "arestemis", "pause", "", generation);
  saveJob(app, record.id, "push", "remove_devices", deniedApproval ? "" : "arestemis", generation);
}

/** Calls the service once: {answered, done, error}. `answered` is false when no HTTP answer came (down, timeout). */
function call(job) {
  const service = job.getString("service");
  const operation = job.getString("operation");
  let path = "/internal/accounts/" + encodeURIComponent(job.getString("account"));
  if (operation === "pause") path += "/pause";
  if (operation === "remove_devices") {
    path += "/devices";
    if (job.getString("app")) path += "/" + encodeURIComponent(job.getString("app"));
  }
  try {
    const res = $http.send({
      method: operation === "pause" ? "POST" : "DELETE",
      url: base(service) + path,
      timeout: TIMEOUT,
      headers: operation === "delete" ? {} : {
        "X-Empire-Access-Generation": String(job.getInt("generation")),
      },
    });
    const done = (res.statusCode >= 200 && res.statusCode < 300) ||
      (operation === "delete" && res.statusCode === 404);
    return { answered: true, done: done, error: done ? "" : "HTTP " + res.statusCode };
  } catch (err) {
    return { answered: false, done: false, error: String(err).slice(0, 500) };
  }
}

/** Mails the superusers (Patrik) about a stuck job; true once sent. */
function alert(app, job) {
  const mail = require(`${__hooks}/lib/mail.js`);
  try {
    return mail.sendToSuperusers(app, mail.deletionStuck({
      account: job.getString("account"),
      service: SERVICES[job.getString("service")].name,
      since: job.getDateTime("created").string(),
      attempts: job.getInt("attempts"),
      error: job.getString("last_error"),
      link: mail.adminLink(app, "deletions", job.id),
      operation: job.getString("operation"),
    }));
  } catch (err) {
    app.logger().error("account deletion alert email failed", "job", job.id, "error", String(err));
    return false;
  }
}

/** A result never reopens a job superseded while its HTTP call was in progress. */
function saveOutcome(app, job, outcome, retryAt) {
  let saved = null;
  app.runInTransaction((txApp) => {
    const current = txApp.findRecordById("deletions", job.id);
    if (current.getBool("done")) return;
    if (outcome) {
      current.set("attempts", current.getInt("attempts") + 1);
      current.set("done", outcome.done);
      current.set("last_error", outcome.error);
    }
    current.set("next_attempt", current.getBool("done") ? "" : retryAt);
    txApp.save(current);
    saved = current;
  });
  return saved;
}

/** Each service has its own batch; retries sort after jobs that have never been attempted. */
function run(app) {
  const now = Date.now();
  const retryAt = timestamp(now + RETRY_SECONDS * 1000);
  for (const service of Object.keys(SERVICES)) {
    let silent = false;
    const filter = "done = false && service = '" + service + "' && " +
      "(next_attempt = '' || next_attempt <= {:now})";
    const jobs = app.findRecordsByFilter("deletions", filter, "next_attempt,created", BATCH, 0,
      { now: timestamp(now) });
    for (const job of jobs) {
      if (job.getBool("done")) continue;
      const operation = job.getString("operation");
      if (operation !== "delete" && !(service === "arestemis" && operation === "pause") &&
          !(service === "push" && operation === "remove_devices")) continue;
      const outcome = silent ? null : call(job);
      if (outcome && !outcome.answered) silent = true;
      const saved = saveOutcome(app, job, outcome, retryAt);
      if (saved && !saved.getBool("done") && !saved.getBool("reported") &&
          now / 1000 - saved.getDateTime("created").unix() >= ALERT_AFTER && alert(app, saved)) {
        app.runInTransaction((txApp) => {
          const current = txApp.findRecordById("deletions", saved.id);
          current.set("reported", true);
          txApp.save(current);
        });
      }
    }
  }
}

module.exports = { SERVICES, base, plan, planAccess, accessChanged, mergeAccess, run };
