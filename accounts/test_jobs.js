const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

let sequence = 0;

class Record {
  constructor(values = {}) {
    this.values = { created: new Date().toISOString(), ...values };
    this.id = values.id || "fixture" + sequence++;
  }

  set(key, value) { this.values[key] = value; }
  getString(key) { return this.values[key] || ""; }
  getInt(key) { return this.values[key] || 0; }
  getBool(key) { return Boolean(this.values[key]); }
  getStringSlice(key) { return this.values[key] || []; }
  getDateTime(key) {
    const value = this.values[key];
    return { unix: () => Date.parse(value) / 1000, string: () => value };
  }
}

function fixture(rows = []) {
  const calls = [];
  const app = {
    rows,
    fail: false,
    findCollectionByNameOrId: () => ({}),
    logger: () => ({ error() {}, warn() {} }),
    save(job) {
      if (this.fail) throw new Error("Injected save failure");
      if (!rows.includes(job)) rows.push(job);
    },
    findRecordById(collection, id) { return rows.find((job) => job.id === id); },
    runInTransaction(fn) { fn(this); },
    findRecordsByFilter(collection, filter, sort, limit, offset, params = {}) {
      const service = /service = '([^']+)'/.exec(filter)?.[1];
      let selected = rows.filter((job) => !job.getBool("done") &&
        (!service || job.getString("service") === service) &&
        (!params.account || job.getString("account") === params.account) &&
        (!filter.includes("operation != 'delete'") || job.getString("operation") !== "delete"));
      if (filter.includes("next_attempt")) {
        selected = selected.filter((job) => !job.getString("next_attempt") ||
          Date.parse(job.getString("next_attempt")) <= Date.now());
      }
      const fields = sort.split(",");
      selected.sort((a, b) => {
        for (const field of fields) {
          const order = a.getString(field).localeCompare(b.getString(field));
          if (order) return order;
        }
        return 0;
      });
      return selected.slice(offset, limit ? offset + limit : undefined);
    },
  };
  const context = {
    module: { exports: {} }, Record,
    __hooks: path.join(__dirname, "pb_hooks"),
    require,
    $os: { getenv: () => "" },
    $http: { send(request) {
      calls.push(request);
      return { statusCode: request.url.includes(":8097") ? 503 : 204 };
    } },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "pb_hooks/lib/deletions.js"), "utf8"), context);
  return { app, jobs: context.module.exports, calls, http: context.$http };
}

test("restoring access supersedes pending jobs", () => {
  const { app, jobs } = fixture();
  const before = new Record({ id: "user1", approved: true, services: ["arestemis"], access_generation: 0 });
  const denied = new Record({ id: "user1", approved: false, services: ["arestemis"], access_generation: 1 });
  jobs.planAccess(app, before, denied);
  jobs.planAccess(app, denied, new Record({
    id: "user1", approved: true, services: ["arestemis"], access_generation: 2,
  }));
  assert.equal(app.rows.length, 2);
  assert.ok(app.rows.every((job) => job.getBool("done")));
});

test("job insertion errors reach the surrounding account transaction", () => {
  const { app, jobs } = fixture();
  app.fail = true;
  assert.throws(() => jobs.planAccess(app,
    new Record({ approved: true, services: ["arestemis"] }),
    new Record({ approved: false, services: ["arestemis"], access_generation: 1 })), /Injected save failure/);
});

test("an unavailable service does not prevent push jobs from running", () => {
  const rows = Array.from({ length: 201 }, (_, index) => new Record({
    account: "old" + index, service: "arestemis", operation: "delete",
    created: new Date(Date.now() - 3600000 + index).toISOString(),
  }));
  const push = new Record({ account: "later", service: "push", operation: "delete" });
  rows.push(push);
  const { app, jobs } = fixture(rows);
  for (let run = 0; run < 3; run++) jobs.run(app);
  assert.equal(push.getBool("done"), true);
  assert.equal(push.getInt("attempts"), 1);
  assert.ok(rows[200].getInt("attempts") > 0);
});

test("later jobs of the same service get a turn before scheduled retries", () => {
  const rows = Array.from({ length: 201 }, (_, index) => new Record({
    account: "old" + index, service: "arestemis", operation: "delete",
    created: new Date(Date.now() - 3600000 + index).toISOString(),
  }));
  const { app, jobs, calls } = fixture(rows);
  jobs.run(app);
  const later = new Record({ account: "newer", service: "arestemis", operation: "delete" });
  rows.push(later);
  jobs.run(app);
  assert.equal(later.getInt("attempts"), 1);
  assert.equal(calls.length, 202);
  assert.ok(rows[0].getString("next_attempt"));
});

test("completion of an in-flight call does not reopen a superseded job", () => {
  const { app, jobs, http } = fixture();
  const allowed = new Record({ id: "account", approved: true, services: ["arestemis"], access_generation: 0 });
  const denied = new Record({ id: "account", approved: false, services: ["arestemis"], access_generation: 1 });
  const restored = new Record({ id: "account", approved: true, services: ["arestemis"], access_generation: 2 });
  jobs.planAccess(app, allowed, denied);
  http.send = () => {
    jobs.planAccess(app, denied, restored);
    return { statusCode: 503 };
  };
  jobs.run(app);
  assert.ok(app.rows.every((job) => job.getBool("done") && job.getBool("superseded")));
});

test("partial restoration carries the current generation and narrower device scope", () => {
  const { app, jobs, calls } = fixture();
  const allowed = new Record({ id: "account", approved: true, services: ["arestemis"], access_generation: 0 });
  const denied = new Record({ id: "account", approved: false, services: ["arestemis"], access_generation: 1 });
  const partial = new Record({ id: "account", approved: true, services: ["empire"], access_generation: 2 });
  jobs.planAccess(app, allowed, denied);
  jobs.planAccess(app, denied, partial);
  assert.ok(app.rows.slice(0, 2).every((job) => job.getBool("superseded")));
  assert.equal(app.rows[3].getString("app"), "arestemis");
  jobs.run(app);
  assert.equal(calls.length, 2);
  assert.ok(calls.every((request) => request.headers["X-Empire-Access-Generation"] === "2"));
});

test("an older profile save keeps current access fields", () => {
  const { jobs } = fixture();
  const before = new Record({ approved: true, services: ["empire", "arestemis"] });
  const current = new Record({ approved: false, services: ["empire"] });
  const older = new Record({ approved: true, services: ["empire", "arestemis"], name: "Changed" });
  jobs.mergeAccess(before, current, older);
  assert.equal(jobs.accessChanged(current, older), false);
});

test("an older service edit preserves a newer approval decision", () => {
  const { jobs } = fixture();
  const before = new Record({ approved: true, services: ["empire", "arestemis"] });
  const current = new Record({ approved: false, services: ["empire", "arestemis"] });
  const older = new Record({ approved: true, services: ["empire"] });
  jobs.mergeAccess(before, current, older);
  assert.equal(older.getBool("approved"), false);
  assert.equal(jobs.accessChanged(current, older), true);
  assert.equal(older.getStringSlice("services").join(","), "empire");
});

test("leaving an app saves the account's current lists, read in the same transaction", () => {
  const routes = {};
  const ignore = () => {};
  const context = {
    module: { exports: {} },
    __hooks: path.join(__dirname, "pb_hooks"),
    require,
    onRecordCreate: ignore, onRecordUpdate: ignore, onRecordCreateRequest: ignore, onRecordUpdateRequest: ignore,
    routerUse: ignore,
    routerAdd: (method, route, handler) => { routes[method + " " + route] = handler; },
    $apis: { requireAuth: () => null },
    ForbiddenError: Error, BadRequestError: Error,
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "pb_hooks/accounts.pb.js"), "utf8"), context);
  // An administrator took Arestemis away while the request ran: a read outside the transaction would still see it.
  const stale = new Record({ id: "user1", services: ["empire", "arestemis"], requested: [] });
  const current = new Record({ id: "user1", services: ["empire"], requested: [] });
  const users = { fields: { getByName: () => ({ values: ["empire", "arestemis", "aresus"] }) } };
  const saved = [];
  const transaction = {
    findRecordById: () => current,
    findCollectionByNameOrId: () => users,
    save: (record) => saved.push(record),
  };
  const app = {
    findRecordById: () => stale,
    findCollectionByNameOrId: () => users,
    save: (record) => saved.push(record),
    runInTransaction: (fn) => fn(transaction),
  };
  const e = {
    app,
    auth: { id: "user1", getBool: () => false },
    requestInfo: () => ({ body: { service: "empire" } }),
    json: (status, body) => ({ status, body }),
  };
  const answer = routes["POST /api/empire/leave"](e);
  assert.deepEqual(saved.map((record) => record.getStringSlice("services")), [[]]);
  // The handler runs in another context, so its objects are compared as JSON.
  assert.equal(JSON.stringify(answer), JSON.stringify({ status: 200, body: { services: [], requested: [] } }));
});
