/* Ares Empire — the orbital ring (window.Ring).

   A true 3D carousel built on CSS transforms (no WebGL). Every province is a tab on a
   horizontal circle; the front one faces you, the one opposite sits at the back. Spin it by
   dragging, scrolling, or with ← / →. One tab is CONQUER — the empty throne. A `stars` prop
   scatters the whole ring into a constellation.

   Props: { projects, starsMode, onActivate(tab), onConquer(), risingSlug } */
(function () {
  const { useState, useRef, useEffect, useMemo, useCallback } = React;
  const TAB_W = 190;               // keep in step with .ring-tab width in styles.css
  const SENS = 0.34;               // degrees of spin per pixel dragged
  const norm = (d) => { d = ((d + 180) % 360 + 360) % 360 - 180; return d; };   // → (-180,180]

  function statusClass(tone) {
    return { live: "st-live", wip: "st-wip", hold: "st-hold", scout: "st-scout" }[tone] || "st-scout";
  }

  function TabInner({ tab, rising }) {
    const S = (window.EMPIRE && window.EMPIRE.STATUS) || {};
    const st = tab.type === "project" ? (S[tab.status] || null) : null;
    const [imgErr, setImgErr] = useState(false);   // missing logo → gold monogram
    return (
      <div className={"tab-inner" + (rising ? " rising" : "")}>
        {tab.type === "conquer" ? (
          <div className="conquer-mark"><window.Icon name="swords" size={34} /></div>
        ) : (
          <div className="tab-logo">
            {tab.logo && !imgErr
              ? <img src={tab.logo} alt={tab.name} onError={() => setImgErr(true)} />
              : <div className="tab-mono">{(tab.name || "?")[0]}</div>}
          </div>
        )}
        <div className="star-node" />
        <div className="tab-name">{tab.name}</div>
        {st && (
          <div className={"tab-status " + statusClass(st.tone)}>
            <span className="dot" />{st.label}
          </div>
        )}
      </div>
    );
  }

  function Ring({ projects, starsMode, onActivate, onConquer, risingSlug }) {
    // tabs = the provinces in orbit + the CONQUER throne
    const tabs = useMemo(() => {
      const t = (projects || []).map((p) => ({ type: "project", ...p }));
      t.push({ type: "conquer", slug: "__conquer", name: "CONQUER" });
      return t;
    }, [projects]);
    const count = tabs.length;
    const step = 360 / count;

    // radius grows with the number of provinces so tabs never crowd
    const radius = Math.max(330, (TAB_W * 1.18) / (2 * Math.tan(Math.PI / count)));

    const [rotation, setRotation] = useState(0);
    const [settling, setSettling] = useState(true);
    const drag = useRef({ on: false, startX: 0, startRot: 0, moved: 0 });
    const wheelAt = useRef(0);

    const frontIndex = useMemo(() => {
      let best = 0, bestD = Infinity;
      for (let i = 0; i < count; i++) {
        const d = Math.abs(norm(rotation + i * step));
        if (d < bestD) { bestD = d; best = i; }
      }
      return best;
    }, [rotation, count, step]);

    // bring base index i to the front by the shortest arc
    const toFront = useCallback((i) => {
      const p = -rotation / step;                 // current continuous front position
      let delta = (i - p) % count; if (delta > count / 2) delta -= count; if (delta < -count / 2) delta += count;
      setSettling(true); setRotation(-(p + delta) * step);
    }, [rotation, step, count]);

    const stepBy = useCallback((n) => {
      const k = Math.round(-rotation / step);
      setSettling(true); setRotation(-(k + n) * step);
    }, [rotation, step]);

    // ---- drag to spin ----
    const onPointerDown = (e) => {
      // NOTE: deliberately NO setPointerCapture — capturing on the scene would steal the
      // click event from the tabs (a known gotcha), breaking tap-to-focus / tap-to-open.
      // Drag still tracks fine via pointermove bubbling up to the scene.
      drag.current = { on: true, startX: e.clientX, startRot: rotation, moved: 0 };
      setSettling(false);
    };
    const onPointerMove = (e) => {
      if (!drag.current.on) return;
      const dx = e.clientX - drag.current.startX;
      drag.current.moved = Math.max(drag.current.moved, Math.abs(dx));
      setRotation(drag.current.startRot + dx * SENS);
    };
    const endDrag = () => {
      if (!drag.current.on) return;
      drag.current.on = false;
      const k = Math.round(-rotation / step);     // snap to nearest tab
      setSettling(true); setRotation(-k * step);
    };

    const onWheel = (e) => {
      const now = Date.now();
      if (now - wheelAt.current < 240) return;
      wheelAt.current = now;
      const d = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
      stepBy(d > 0 ? 1 : -1);
    };

    useEffect(() => {
      const onKey = (e) => {
        if (e.key === "ArrowRight") { stepBy(1); }
        else if (e.key === "ArrowLeft") { stepBy(-1); }
      };
      window.addEventListener("keydown", onKey);
      return () => window.removeEventListener("keydown", onKey);
    }, [stepBy]);

    const clickTab = (i, tab) => {
      if (drag.current.moved > 6) return;          // it was a spin, not a tap
      if (i !== frontIndex) { toFront(i); return; }
      if (tab.type === "conquer") onConquer && onConquer();
      else onActivate && onActivate(tab);
    };

    // ---- stars-mode scatter positions (deterministic per index) ----
    const stars = useMemo(() => {
      const W = window.innerWidth, H = window.innerHeight, R = Math.min(W, H);
      return tabs.map((_, i) => {
        const a = (i * 137.508) * Math.PI / 180;
        const r = (0.2 + ((i * 0.11) % 0.24)) * R;
        return { x: Math.cos(a) * r * 1.35, y: Math.sin(a) * r * 0.82 };
      });
    }, [tabs]);

    return (
      <div className={"ring-scene" + (starsMode ? " stars" : "")}
           onPointerDown={onPointerDown} onPointerMove={onPointerMove}
           onPointerUp={endDrag} onPointerLeave={endDrag} onWheel={onWheel}>
        <div className={"ring" + (settling ? " settling" : "")}
             style={{ transform: starsMode ? "none" : `translateZ(-${radius}px) rotateY(${rotation}deg)` }}>
          {tabs.map((tab, i) => {
            const world = norm(rotation + i * step);
            const depth = Math.abs(world) / 180;
            const behind = Math.abs(world) > 90;
            const transform = starsMode
              ? `translate3d(${stars[i].x}px, ${stars[i].y}px, 0)`
              : `rotateY(${i * step}deg) translateZ(${radius}px)`;
            return (
              <div key={tab.slug}
                   className={"ring-tab"
                     + (i === frontIndex ? " is-front" : "")
                     + (behind && !starsMode ? " behind" : "")
                     + (tab.type === "conquer" ? " is-conquer" : "")}
                   style={{ transform, "--depth": starsMode ? 0 : depth }}
                   onClick={() => clickTab(i, tab)}>
                <TabInner tab={tab} rising={tab.slug === risingSlug} />
              </div>
            );
          })}
        </div>

        {!starsMode && (
          <div className="ring-hint">
            <span>drag</span><span>·</span><kbd>←</kbd><kbd>→</kbd><span>·</span><span>scroll to spin</span>
          </div>
        )}
      </div>
    );
  }

  window.Ring = Ring;
})();
