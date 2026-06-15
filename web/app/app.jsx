/* Ares Empire — the hub (window.EmpireApp).

   Composes the throne room: the eclipse sky (moon4 + corona + drifting stars + mouse
   parallax) behind everything, the Oracle bust top-left, the gold ARES EMPIRE crown
   top-center, the runes (stars mode · war council · chronicle) top-right, the orbital
   ring at the centre, and the big gold wordmark band at the bottom. Panels + the CONQUER
   forge mount over it. */
(function () {
  const { useState, useEffect, useRef, useCallback } = React;

  function EmpireApp() {
    const E = window.EMPIRE || {};
    const [projects, setProjects] = useState(() => (E.projects || []).slice());
    const [stars, setStars] = useState(false);
    const [panel, setPanel] = useState(null);        // "oracle" | "council" | "chronicle" | "forge" | null
    const [forgeInit, setForgeInit] = useState(null);
    const [rising, setRising] = useState(null);
    const moonRef = useRef(null);

    useEffect(() => { try { window.lucide && window.lucide.createIcons(); } catch (_) {} });

    // mouse parallax on the eclipse (skipped under reduced-motion)
    useEffect(() => {
      let reduced = false;
      try { reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (_) {}
      if (reduced) return;
      let raf = 0, tx = 0, ty = 0;
      const onMove = (e) => {
        const nx = e.clientX / window.innerWidth - 0.5, ny = e.clientY / window.innerHeight - 0.5;
        tx = nx * -16; ty = ny * -16;
        if (!raf) raf = requestAnimationFrame(() => {
          raf = 0; if (moonRef.current) moonRef.current.style.transform = `translate3d(${tx}px, ${ty}px, 0)`;
        });
      };
      window.addEventListener("pointermove", onMove);
      return () => { window.removeEventListener("pointermove", onMove); if (raf) cancelAnimationFrame(raf); };
    }, []);

    const moonSrc = (E.sky && E.sky.moon) || "brand/moon4.png";

    const activate = useCallback((tab) => { if (tab.url) window.open(tab.url, "_blank", "noopener"); }, []);
    const openForge = useCallback((init) => { setForgeInit(init || null); setPanel("forge"); }, []);

    const conquered = useCallback((proj) => {
      setProjects((prev) => prev.some((p) => p.slug === proj.slug) ? prev : prev.concat(proj));
      // optimistic Chronicle entry so the scroll reflects the new conquest immediately
      try {
        (window.EMPIRE.chronicle = window.EMPIRE.chronicle || []).unshift({
          at: new Date().toISOString().slice(0, 10), project: proj.slug,
          text: `Marched on ${proj.name}: charter forged, throne raised. Conquest underway.`,
        });
      } catch (_) {}
      setPanel(null); setStars(false); setRising(proj.slug);
      setTimeout(() => setRising(null), 1200);
    }, []);

    return (
      <React.Fragment>
        {/* ---- the sky ---- */}
        <div className="emp-sky" aria-hidden="true">
          <div className="emp-stars" />
          <div className="emp-moon-wrap" ref={moonRef}>
            <img className="emp-moon" src={moonSrc} alt="" onError={(e) => { e.target.style.display = "none"; }} />
            <div className="emp-corona" />
          </div>
        </div>

        {/* ---- the hub ---- */}
        <main className="emp-app">
          <header className="emp-top">
            <button className="emp-oracle-btn" onClick={() => setPanel("oracle")} title="Consult the Oracle">
              <span className="emp-oracle-face"><window.Bust label="ARES" /></span>
              <span className="emp-oracle-meta">
                <span className="emp-oracle-k">THE ORACLE</span>
                <span className="emp-oracle-s">Consult Ares</span>
              </span>
            </button>

            <div className="emp-crown shimmer">ARES EMPIRE</div>

            <nav className="emp-runes">
              <button className={"emp-rune" + (stars ? " on" : "")} onClick={() => setStars((s) => !s)}
                      title={stars ? "Return to the ring" : "Stars mode"} aria-pressed={stars}>
                <window.Icon name="sparkles" />
              </button>
              <button className="emp-rune" onClick={() => setPanel("council")} title="War Council — ideas">
                <window.Icon name="compass" />
              </button>
              <button className="emp-rune" onClick={() => setPanel("chronicle")} title="The Chronicle — changelog">
                <window.Icon name="scroll-text" />
              </button>
            </nav>
          </header>

          <section className="emp-stage">
            <window.Ring projects={projects} starsMode={stars}
                         onActivate={activate} onConquer={() => openForge(null)} risingSlug={rising} />
          </section>

          <footer className="emp-band">
            <window.Wordmark text="ARES EMPIRE" shimmer />
          </footer>
        </main>

        {/* ---- overlays ---- */}
        {panel === "oracle" && <window.Oracle onClose={() => setPanel(null)} onCouncil={() => setPanel("council")} />}
        {panel === "council" && <window.WarCouncil onClose={() => setPanel(null)}
                                  onPromote={(idea) => openForge(idea)} />}
        {panel === "chronicle" && <window.Chronicle onClose={() => setPanel(null)} />}
        {panel === "forge" && <window.Forge initial={forgeInit} onClose={() => setPanel(null)} onConquered={conquered} />}
      </React.Fragment>
    );
  }

  window.EmpireApp = EmpireApp;
})();
