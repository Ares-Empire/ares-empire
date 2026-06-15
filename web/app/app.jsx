/* Ares Empire — the hub (window.EmpireApp).

   A clean, pure-black room: a dark marble bust (transparent cut-out) at the left edge, the
   Ares crest top-left, and — offset up & right — the orbital circle of provinces with the
   chronicle log (a golden line + radiating dust, busts as markers) under it on the right.
   The default screen is THE EMPIRE; clicking the title (or a province) opens the PROJECTS
   board and clicking PROJECTS returns. The EXPAND control swaps the stage to the EXPANSIONS
   board (the plans). */
(function () {
  const { useState, useEffect, useCallback } = React;

  function EmpireApp() {
    const E = window.EMPIRE || {};
    const [projects, setProjects] = useState(() => (E.projects || []).slice());
    const [view, setView] = useState("projects");      // "projects" | "expansions"
    const [spread, setSpread] = useState(false);        // projects: circle (false) vs board (true)
    const [forge, setForge] = useState(null);           // null | { open, init }
    const [rising, setRising] = useState(null);
    const [detail, setDetail] = useState(null);         // null | { project, rect } — the full-screen province page

    useEffect(() => { try { window.lucide && window.lucide.createIcons(); } catch (_) {} });

    const ideas = E.ideas || [];
    const chronicle = E.chronicle || [];

    // leave the hub for a province — via the empire SSO mint (/sso?to=<slug>), which signs a
    // short-lived hand-off token so the province starts a session with no second login. Falls
    // back to the raw URL for anything without a slug.
    const goTo = useCallback((p) => {
      if (!p) return;
      if (p.slug) window.location.assign("/sso?to=" + encodeURIComponent(p.slug));
      else if (p.url) window.location.assign(p.url);
    }, []);
    const openDetail = useCallback((p, rect) => setDetail({ project: p, rect }), []);
    const openForge = useCallback((init) => setForge({ open: true, init: init || null }), []);

    const toggleView = useCallback(() => {
      setView((v) => (v === "projects" ? "expansions" : "projects"));
      setSpread(false);
    }, []);

    const conquered = useCallback((proj) => {
      setProjects((prev) => (prev.some((p) => p.slug === proj.slug) ? prev : prev.concat(proj)));
      try {
        (window.EMPIRE.chronicle = window.EMPIRE.chronicle || []).unshift({
          at: new Date().toISOString().slice(0, 10), project: proj.slug,
          text: `Began ${proj.name}: charter forged, added to the circle. Build underway.`,
        });
      } catch (_) {}
      setForge(null); setView("projects"); setSpread(false); setRising(proj.slug);
      setTimeout(() => setRising(null), 1100);
    }, []);

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
          <img src="brand/head_transparent_real.png" alt="" onError={(e) => { e.target.style.display = "none"; }} />
        </div>

        <main className="emp-app">
          <header className="emp-top">
            <div className="emp-top-l">
              <img className="emp-crest" src="brand/ares_transparent.png" alt="Ares Empire"
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
              <window.Ring projects={projects} onOpen={goTo} risingSlug={rising} />
            )}
          </section>

          {!expanded && !spread && <window.Chronicle log={chronicle} projects={projects} />}
        </main>

        {forge && forge.open && (
          <window.Forge initial={forge.init} onClose={() => setForge(null)} onConquered={conquered} />
        )}

        {detail && (
          <window.ProjectDetail project={detail.project} originRect={detail.rect}
                                onClose={() => setDetail(null)} onVisit={goTo} />
        )}
      </React.Fragment>
    );
  }

  window.EmpireApp = EmpireApp;
})();
