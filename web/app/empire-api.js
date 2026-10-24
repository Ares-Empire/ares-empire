/* Shared transport for the two hub trees. Localhost previews fetch JSON fixtures;
   sample actions stay in memory. Other hosts always use the account API. */
(function () {
  const sampleMode = location.hostname === "localhost" || location.hostname === "127.0.0.1";
  const params = new URLSearchParams(location.search);
  let sample;
  let sampleLoading;
  let sampleChronicle;
  let pending = [
    { id: "sample-robin", email: "robin@example.com", name: "Robin Vale", created: "2026-10-24T08:40:00Z" },
    { id: "sample-alex", email: "alex@example.com", name: "Alex Rowan", created: "2026-10-23T17:15:00Z" },
  ];
  const clone = (value) => JSON.parse(JSON.stringify(value));

  async function sampleData() {
    if (!sampleLoading) {
      const role = params.get("as") === "user" ? "user" : "admin";
      sampleLoading = request("app/samples/empire." + role + ".json").then(validate).then((data) => {
        sample = data;
        sampleChronicle = data.chronicle.slice();
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
      const error = new Error(({401: "Your session has ended. Please log in again.", 403: "This account does not have access.",
        503: "The Empire is temporarily unavailable. Try again shortly."})[response.status] || "That action could not be completed. Please try again.");
      error.status = response.status;
      throw error;
    }
    if (response.status === 204) return null;
    // The approval action has no response-body contract; accept an empty body.
    const text = await response.text();
    try { return text ? JSON.parse(text) : null; }
    catch (_) { throw new Error("The Empire could not load. Please try again shortly."); }
  }

  function validate(data) {
    if (!data || data.version !== 2 || !data.me || typeof data.me.admin !== "boolean" ||
        !["projects", "addable", "chronicle", "ideas"].every((key) => Array.isArray(data[key])) ||
        typeof data.pending !== "number") throw new Error("The Empire could not load. Please try again shortly.");
    return data;
  }

  window.EmpireData = {
    sampleMode,
    skipIntro: sampleMode && params.has("skipIntro"),
    initial: () => sampleMode && sample ? clone(sample) : null,
    load: async () => sampleMode ? clone(await sampleData()) : request("/api/empire"),
    validate,
    async ring(change) {
      if (!sampleMode) return validate(await request("/api/empire/ring", change));
      const data = await sampleData();
      if (data.me.admin) throw new Error("The admin ring already contains every province.");
      if (change.add) {
        const province = data.addable.find((p) => p.slug === change.add);
        if (!province) throw new Error("This province is no longer available.");
        data.projects.push(province);
        data.addable = data.addable.filter((p) => p.slug !== change.add);
      } else if (change.remove) {
        const province = data.projects.find((p) => p.slug === change.remove);
        if (province) data.addable.push(province);
        data.projects = data.projects.filter((p) => p.slug !== change.remove);
      }
      data.chronicle = sampleChronicle.filter((entry) => data.projects.some((p) => p.slug === entry.project));
      return clone(data);
    },
    async approvals() {
      if (!sampleMode) {
        const result = await request("/api/empire/approvals");
        if (!Array.isArray(result)) throw new Error("Pending accounts could not be loaded. Please try again.");
        return result;
      }
      if (!(await sampleData()).me.admin) throw new Error("Approvals are only available to admins.");
      return clone(pending);
    },
    async decide(id, decision) {
      if (!sampleMode) return request("/api/empire/approvals/" + encodeURIComponent(id), decision);
      const data = await sampleData();
      if (!data.me.admin) throw new Error("Approvals are only available to admins.");
      pending = pending.filter((account) => account.id !== id);
      data.pending = pending.length;
    },
    destination(province) {
      // Connections in EMPIRE.md: only Aresium currently uses the hub hand-off.
      return province.state === "coming-soon" ? null : province.slug === "aresium"
        ? "/sso?to=" + encodeURIComponent(province.slug) : province.url || null;
    },
  };
})();
