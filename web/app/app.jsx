/* Ares Empire — the hub (window.EmpireApp).

   A clean, near-black room: ambient Mars-red/steel-blue wash, a marble bust standing at the
   left edge, and — offset up & right — the orbital circle of provinces with the chronicle
   timeline beneath it. The EXPAND control swaps the stage to the EXPANSIONS board (the plans);
   clicking the focused province spreads the circle into the project board. */
(function () {
  const { useState, useEffect, useCallback } = React;

  function EmpireApp() {
    const E = window.EMPIRE || {};
    const [projects, setProjects] = useState(() => (E.projects || []).slice());
    const [view, setView] = useState("projects");      // "projects" | "expansions"
    const [spread, setSpread] = useState(false);        // projects: circle (false) vs board (true)
    const [forge, setForge] = useState(null);           // null | { open, init }
    const [rising, setRising] = useState(null);

    useEffect(() => { try { window.lucide && window.lucide.createIcons(); } catch (_) {} });

    const ideas = E.ideas || [];
    const chronicle = E.chronicle || [];

    const visit = useCallback((p) => { if (p && p.url) window.open(p.url, "_blank", "noopener"); }, []);
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

    return (
      <React.Fragment>
        <div className="emp-ambient" aria-hidden="true" />
        <div className={"emp-figure" + (expanded || spread ? " recede" : "")} aria-hidden="true">
          <img src="brand/head1.png" alt="" onError={(e) => { e.target.style.display = "none"; }} />
        </div>

        <main className="emp-app">
          <header className="emp-top">
            <div className="emp-top-l" />
            <h1 className="emp-title">{expanded ? "EXPANSIONS" : "PROJECTS"}</h1>
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
              <window.CardGrid items={projects} kind="project" onBack={() => setSpread(false)} onVisit={visit} />
            ) : (
              <window.Ring projects={projects} onSpread={() => setSpread(true)} risingSlug={rising} />
            )}
          </section>

          {!expanded && !spread && <window.Timeline log={chronicle} />}
        </main>

        {forge && forge.open && (
          <window.Forge initial={forge.init} onClose={() => setForge(null)} onConquered={conquered} />
        )}
      </React.Fragment>
    );
  }

  window.EmpireApp = EmpireApp;
})();
