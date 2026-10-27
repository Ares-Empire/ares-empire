/* Ares Empire — the hub (window.EmpireApp).

   A clean, pure-black room: a dark marble bust (transparent cut-out) at the left edge, the
   Ares crest top-left, and — offset up & right — the orbital circle of provinces with the
   chronicle log (a golden line + radiating dust, busts as markers) under it on the right.
   The default screen is THE EMPIRE; clicking the title (or a province) opens the PROJECTS
   board and clicking PROJECTS returns. The EXPAND control swaps the stage to the EXPANSIONS
   board (the plans). A member's wheel ends in a "+" place: the other apps open to users, to ask for access. */
(function () {
  const { useState, useEffect, useCallback } = React;

  function EmpireApp() {
    const [data, setData] = useState(() => window.EMPIRE || {});
    const [projects, setProjects] = useState(() => ((window.EMPIRE || {}).projects || []).slice());
    const [view, setView] = useState("projects");      // "projects" | "expansions"
    const [spread, setSpread] = useState(false);        // projects: circle (false) vs board (true)
    const [forge, setForge] = useState(null);           // null | { open, init }
    const [rising, setRising] = useState(null);
    const [detail, setDetail] = useState(null);         // null | { project, rect } — the full-screen province page
    const [more, setMore] = useState(null);             // null | { asking, error } — a member's "+" (More apps)

    useEffect(() => { try { window.lucide && window.lucide.createIcons(); } catch (_) {} });

    // live data from the hub API (GET /api/empire), updated by the `empire` CLI / git hooks.
    // Falls back silently to the embedded empire-data.js seed when the API isn't reachable.
    useEffect(() => {
      let alive = true;
      window.EmpireData.load()
        .then((d) => {
          if (alive && d && Array.isArray(d.projects)) {
            // merge over the seed (don't replace) so seed-only keys the live data omits —
            // notably the STATUS vocabulary the ring/detail render from — survive.
            const merged = { ...(window.EMPIRE || {}), ...d };
            window.EMPIRE = merged; setData(merged); setProjects(merged.projects.slice());
          }
        })
        .catch(() => {});
      return () => { alive = false; };
    }, []);

    const ideas = data.ideas || [];
    const chronicle = data.chronicle || [];

    const openDetail = useCallback((p, rect) => setDetail({ project: p, rect }), []);
    // leave the hub for a province (EmpireData.destination: Aresium through the hub's hand-off, /sso?to=aresium, so
    // it needs no second login; others their website), in a new tab so the hub stays put. A province without a
    // website opens its page instead.
    const goTo = useCallback((p) => {
      if (!p) return;
      const dest = window.EmpireData.destination(p);
      if (dest) window.open(dest, "_blank", "noopener");
      else setDetail({ project: p, rect: null });
    }, []);

    // A member asks for one app of the "+"; the answer is the fresh hub data (the app now "asked").
    const ask = useCallback(async (service) => {
      setMore((m) => ({ ...m, asking: service, error: null }));
      try {
        const answer = await window.EmpireData.ask(service);
        const merged = { ...(window.EMPIRE || {}), ...answer };
        window.EMPIRE = merged; setData(merged); setProjects(merged.projects.slice());
        setMore((m) => m && { ...m, asking: null });
      } catch (err) {
        setMore((m) => m && { ...m, asking: null, error: err.message });
      }
    }, []);
    const openForge = useCallback((init) => setForge({ open: true, init: init || null }), []);

    const toggleView = useCallback(() => {
      setView((v) => (v === "projects" ? "expansions" : "projects"));
      setSpread(false);
    }, []);

    const conquered = useCallback((proj) => {
      setProjects((prev) => (prev.some((p) => p.slug === proj.slug) ? prev : prev.concat(proj)));
      setData((d) => {
        const entry = { at: new Date().toISOString().slice(0, 10), project: proj.slug,
          text: `Began ${proj.name}: charter forged, added to the circle. Build underway.` };
        const next = { ...d, chronicle: [entry, ...(d.chronicle || [])] };
        window.EMPIRE = next;
        return next;
      });
      setForge(null); setView("projects"); setSpread(false); setRising(proj.slug);
      setTimeout(() => setRising(null), 1100);
    }, []);

    const member = !!(data.me && data.me.admin === false);
    const expanded = view === "expansions";
    const home = !expanded && !spread;                  // the default screen: THE EMPIRE
    const titleText = expanded ? "EXPANSIONS" : spread ? "PROJECTS" : "THE EMPIRE";

    // the title is the primary toggle: THE EMPIRE (default) ⇄ PROJECTS (the board)
    const onTitle = useCallback(() => {
      if (expanded) { setView("projects"); setSpread(false); return; }
      setSpread((s) => !s);
    }, [expanded]);

    return (
      <React.Fragment>
        <div className="emp-ambient" aria-hidden="true" />
        <div className={"emp-figure" + (expanded || spread ? " recede" : "")} aria-hidden="true">
          <img src="brand/head_transparent_real.webp" alt="" onError={(e) => { e.target.style.display = "none"; }} />
        </div>

        <main className="emp-app">
          <header className="emp-top">
            <div className="emp-top-l">
              <img className="emp-crest" src="brand/ares_transparent.webp" alt="Ares Empire"
                   onError={(e) => { e.target.style.display = "none"; }} />
            </div>
            <button className={"emp-title" + (home ? " is-empire" : "")} onClick={onTitle}
                    title={home ? "Open the projects" : "Back to the empire"}>
              {titleText}
            </button>
            <div className="emp-top-r">
              <button className={"emp-toggle" + (expanded ? " on" : "")} onClick={toggleView}
                      title={expanded ? "Back to projects" : "Show the empire's expansions"}>
                {expanded
                  ? <React.Fragment><window.Icon name="orbit" size={15} />Projects</React.Fragment>
                  : <React.Fragment><window.Icon name="maximize-2" size={15} />Expand</React.Fragment>}
              </button>
              <a className="emp-logout" href="/logout" title="Log out"><window.Icon name="log-out" size={16} /></a>
            </div>
          </header>

          <section className="emp-stage">
            {expanded ? (
              <window.CardGrid items={ideas} kind="expansion" onForge={openForge} />
            ) : spread ? (
              <window.CardGrid items={projects} kind="project" onBack={() => setSpread(false)} onOpen={openDetail} />
            ) : (
              <window.Ring projects={projects} onOpen={goTo} risingSlug={rising}
                           addSlot={member && !window.EmpireData.demoMode ? { label: "More apps", onAdd: () => setMore({ asking: null, error: null }) } : undefined} />
            )}
          </section>

          {!expanded && !spread && <window.Chronicle log={chronicle} projects={projects} />}
          <window.LegalLinks className="emp-legal" />
        </main>

        {forge && forge.open && (
          <window.Forge initial={forge.init} onClose={() => setForge(null)} onConquered={conquered} />
        )}

        {detail && (
          <window.ProjectDetail project={detail.project} originRect={detail.rect}
                                onClose={() => setDetail(null)} onVisit={goTo} />
        )}

        {more && (
          <window.MoreApps apps={data.addable || []} asking={more.asking} error={more.error}
                           onAsk={ask} onClose={() => setMore(null)} />
        )}
      </React.Fragment>
    );
  }

  window.EmpireApp = EmpireApp;
})();
