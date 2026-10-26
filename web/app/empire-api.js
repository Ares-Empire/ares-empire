/* Shared transport for the two hub trees. Localhost previews fetch JSON fixtures (web/app/samples, written by
   tools/empire_samples.py --web from the hub server itself); sample actions stay in memory. Other hosts always use the
   account API, except the public demo (/demo, webauth/server.py): the same sample mode with the made-up guest
   (app/samples/empire.demo.json), each app's link from its sample (Aresium's demo, the request form) and a band
   saying it is a demo. */
(function () {
  const demoMode = location.pathname === "/demo";
  const sampleMode = demoMode || location.hostname === "localhost" || location.hostname === "127.0.0.1";
  const params = new URLSearchParams(location.search);
  if (demoMode) {
    document.documentElement.classList.add("demo");
    const band = document.createElement("div");
    band.className = "demo-band";
    band.innerHTML = '<span class="demo-dot"></span><span><b>Demo</b> · a made-up account to look around</span>' +
      '<a href="/login">Log in</a>';
    document.body.appendChild(band);
  }
  // ?as=… picks the preview account: admin (the default), member, new-member or requested.
  const PREVIEWS = ["admin", "member", "new-member", "requested"];
  let sample;
  let sampleLoading;
  let pending;  // the approvals preview (app/samples/approvals.json), changed in memory by decisions
  const clone = (value) => JSON.parse(JSON.stringify(value));

  async function sampleData() {
    if (!sampleLoading) {
      const role = demoMode ? "demo" : PREVIEWS.includes(params.get("as")) ? params.get("as") : "admin";
      sampleLoading = request("app/samples/empire." + role + ".json").then(validate).then((data) => {
        sample = data;
        return data;
      }).catch((error) => {
        sampleLoading = null;
        throw error;
      });
    }
    await sampleLoading;
    return sample;
  }

  async function request(path, body) {
    let response;
    try {
      response = await fetch(path, {
        credentials: "same-origin",
        headers: { "Accept-Language": "en", ...(body ? { "Content-Type": "application/json" } : {}) },
        ...(body ? { method: "POST", body: JSON.stringify(body) } : {}),
      });
    } catch (_) {
      throw new Error("The Empire could not be reached. Check your connection and try again.");
    }
    if (!response.ok) {
      // The hub's own sentence says what was wrong with a request (400, e.g. "This app is not open to requests.").
      let sentence = null;
      try { const answer = await response.json(); if (answer && typeof answer.error === "string") sentence = answer.error; }
      catch (_) {}
      const error = new Error(({401: "Your session has ended. Please log in again.", 403: "This account does not have access.",
        503: "The Empire is temporarily unavailable. Try again shortly."})[response.status] ||
        (response.status === 400 && sentence) || "That action could not be completed. Please try again.");
      error.status = response.status;
      throw error;
    }
    if (response.status === 204) return null;
    // Accept an empty body (sample mode); the approval action answers {ok, approvals, pending}.
    const text = await response.text();
    try { return text ? JSON.parse(text) : null; }
    catch (_) { throw new Error("The Empire could not load. Please try again shortly."); }
  }

  function validate(data) {
    if (!data || data.version !== 2 || !data.me || typeof data.me.admin !== "boolean" ||
        !["projects", "addable", "chronicle", "ideas"].every((key) => Array.isArray(data[key])) ||
        (data.pending !== null && typeof data.pending !== "number")) throw new Error("The Empire could not load. Please try again shortly.");
    return data;
  }

  window.EmpireData = {
    sampleMode,
    demoMode,
    skipIntro: sampleMode && params.has("skipIntro"),
    initial: () => sampleMode && sample ? clone(sample) : null,
    load: async () => sampleMode ? clone(await sampleData()) : request("/api/empire"),
    validate,
    // What the "+" offers for an app the account does not have (docs/API-EMPIRE.md): "ask" (open, not asked for yet),
    // "asked" (waiting for approval) or "soon" (coming soon, cannot be asked for yet).
    offer: (province) => province.access === "requested" ? "asked" : province.state === "open" ? "ask" : "soon",
    // Ask for access to one app of the "+" (POST /api/empire/request); answers the fresh hub data. Patrik approves it.
    async ask(service) {
      if (!sampleMode) return validate(await request("/api/empire/request", { service }));
      const data = await sampleData();
      const app = data.addable.find((p) => p.slug === service);
      if (!app || app.state !== "open") throw new Error("This app is not open to requests.");
      app.access = "requested";
      return clone(data);
    },
    async approvals() {
      if (!sampleMode) {
        const result = await request("/api/empire/approvals");
        if (!Array.isArray(result)) throw new Error("Pending accounts could not be loaded. Please try again.");
        return result;
      }
      if (!(await sampleData()).me.admin) throw new Error("Approvals are only available to admins.");
      if (!pending) pending = await request("app/samples/approvals.json");
      return clone(pending);
    },
    async decide(id, decision) {
      if (!sampleMode) return request("/api/empire/approvals/" + encodeURIComponent(id), decision);
      const data = await sampleData();
      if (!data.me.admin) throw new Error("Approvals are only available to admins.");
      if (!pending) pending = await request("app/samples/approvals.json");
      pending = pending.filter((account) => account.id !== id);
      data.pending = pending.length;
      return { ok: true, approvals: clone(pending), pending: pending.length };
    },
    destination(province) {
      // The demo: each app's own link from the sample (Aresium's demo, the others' request form).
      if (demoMode) return province.url || null;
      // Connections in EMPIRE.md: only Aresium currently uses the hub hand-off.
      return province.state === "coming-soon" ? null : province.slug === "aresium"
        ? "/sso?to=" + encodeURIComponent(province.slug) : province.url || null;
    },
  };
})();
