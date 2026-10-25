// Deleting an account reaches every service that keeps data per account (docs/ACCOUNTS.md → Accounts in every app).
// After a users record is deleted, `plan` writes one job per service into `deletions`; every 5 minutes `run` calls
// each open job: `DELETE <service>/internal/accounts/<id>` on localhost (never routed by Caddy). 2xx or 404 = done,
// anything else is tried again on the next run; a job still failing a day after the deletion is mailed to Patrik once.
// Loaded by the handlers with `require(`${__hooks}/lib/deletions.js`)`.

// The services with per-account data, where they listen on this host, and their names in emails. An environment
// variable may point a service elsewhere (the account rule tests use a fake service); the server uses the defaults.
const SERVICES = {
  arestemis: { name: "Arestemis", env: "ARESTEMIS_INTERNAL_URL", url: "http://127.0.0.1:8097" },
  push: { name: "the push service", env: "PUSH_INTERNAL_URL", url: "http://127.0.0.1:8096" },
};
const ALERT_AFTER = 24 * 60 * 60; // seconds after the deletion
const TIMEOUT = 10; // seconds per call
const BATCH = 200; // open jobs per run, oldest first

function base(service) {
  const entry = SERVICES[service];
  return ($os.getenv(entry.env) || entry.url).replace(/\/+$/, "");
}

/** One open job per service for the deleted account `account` (its id). */
function plan(app, account) {
  const collection = app.findCollectionByNameOrId("deletions");
  for (const service of Object.keys(SERVICES)) {
    try {
      const job = new Record(collection);
      job.set("account", account);
      job.set("service", service);
      job.set("attempts", 0);
      job.set("done", false);
      app.save(job);
    } catch (err) {
      app.logger().error("account deletion job not created", "account", account, "service", service, "error", String(err));
    }
  }
}

/** Calls the service once: {answered, done, error}. `answered` is false when no HTTP answer came (down, timeout). */
function call(service, account) {
  try {
    const res = $http.send({
      method: "DELETE",
      url: base(service) + "/internal/accounts/" + encodeURIComponent(account),
      timeout: TIMEOUT,
    });
    const done = (res.statusCode >= 200 && res.statusCode < 300) || res.statusCode === 404;
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
    }));
  } catch (err) {
    app.logger().error("account deletion alert email failed", "job", job.id, "error", String(err));
    return false;
  }
}

/** One run of the cron: every open job once (a service that did not answer is not called again in this run). */
function run(app) {
  const now = Math.floor(Date.now() / 1000);
  const silent = {};
  for (const job of app.findRecordsByFilter("deletions", "done = false", "created", BATCH, 0)) {
    const service = job.getString("service");
    if (!SERVICES[service]) continue;
    let changed = false;
    if (!silent[service]) {
      const outcome = call(service, job.getString("account"));
      job.set("attempts", job.getInt("attempts") + 1);
      job.set("done", outcome.done);
      job.set("last_error", outcome.error);
      changed = true;
      if (!outcome.answered) silent[service] = true;
      if (!outcome.done) {
        app.logger().warn("account deletion failed", "service", service, "account", job.getString("account"),
          "error", outcome.error);
      }
    }
    if (!job.getBool("done") && !job.getBool("reported") &&
        now - job.getDateTime("created").unix() >= ALERT_AFTER && alert(app, job)) {
      job.set("reported", true);
      changed = true;
    }
    if (changed) app.save(job);
  }
}

module.exports = { SERVICES, plan, run };
