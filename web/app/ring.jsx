/* Ares Empire — the orbital circle (window.Ring).

   A wheel laid flat on a table, seen FROM THE FRONT — so the orbit reads almost as a line.
   The province revolved to the front is sharp and centred; its neighbours fall away to the
   sides (smaller · paler · blurred) and the far side of the wheel is out of sight. Drag /
   scroll / ← → to revolve; click the focused province to open it, click a neighbour to bring
   it round.

   Props: { projects, onOpen(project), risingSlug } */
(function () {
  const { useState, useRef, useEffect, useMemo, useCallback } = React;
  const SENS = 0.34;                   // degrees of revolve per pixel dragged
  const VISIBLE = 104;                 // beyond this many degrees from front, a province is hidden (far side)
  const norm180 = (d) => ((d + 180) % 360 + 360) % 360 - 180;   // → (-180, 180]

  const statusClass = (tone) => ({ live: "st-live", wip: "st-wip", hold: "st-hold", scout: "st-scout", muster: "st-muster" }[tone] || "st-scout");

  function TabFace({ tab }) {
    const S = (window.EMPIRE && window.EMPIRE.STATUS) || {};
    const st = S[tab.status] || null;
    const [imgErr, setImgErr] = useState(false);
    return (
      <React.Fragment>
        <div className="tab-logo">
          {tab.logo && !imgErr
            ? <img src={tab.logo} alt={tab.name} onError={() => setImgErr(true)} />
            : <div className="tab-mono">{(tab.name || "?")[0]}</div>}
        </div>
        <div className="tab-body">
          <div className="tab-name">{tab.name}</div>
          {st && <div className={"tab-status " + statusClass(st.tone)}>{st.label}</div>}
        </div>
      </React.Fragment>
    );
  }

  function Ring({ projects, onOpen, risingSlug }) {
    const tabs = projects || [];
    const count = Math.max(tabs.length, 1);
    const step = 360 / count;

    const [rotation, setRotation] = useState(0);
    const [settling, setSettling] = useState(true);
    const drag = useRef({ on: false, startX: 0, startRot: 0, moved: 0 });
    const wheelAt = useRef(0);
    const sceneRef = useRef(null);
    const [dim, setDim] = useState({ w: 880, h: 300 });

    useEffect(() => {
      const m = () => { const el = sceneRef.current; if (el) setDim({ w: el.offsetWidth, h: el.offsetHeight }); };
      m(); window.addEventListener("resize", m);
      return () => window.removeEventListener("resize", m);
    }, []);

    const frontIndex = useMemo(() => {
      let best = 0, bestD = Infinity;
      for (let i = 0; i < count; i++) { const d = Math.abs(norm180(i * step + rotation)); if (d < bestD) { bestD = d; best = i; } }
      return best;
    }, [rotation, count, step]);

    const stepBy = useCallback((n) => { const k = Math.round(rotation / step); setSettling(true); setRotation((k + n) * step); }, [rotation, step]);
    const toFront = useCallback((i) => { setSettling(true); setRotation(rotation + norm180(-i * step - rotation)); }, [rotation, step]);

    const onPointerDown = (e) => { drag.current = { on: true, startX: e.clientX, startRot: rotation, moved: 0 }; setSettling(false); };
    const onPointerMove = (e) => {
      if (!drag.current.on) return;
      const dx = e.clientX - drag.current.startX;
      drag.current.moved = Math.max(drag.current.moved, Math.abs(dx));
      setRotation(drag.current.startRot + dx * SENS);
    };
    const endDrag = () => { if (!drag.current.on) return; drag.current.on = false; setSettling(true); setRotation(Math.round(rotation / step) * step); };
    const onWheel = (e) => {
      const now = Date.now(); if (now - wheelAt.current < 240) return; wheelAt.current = now;
      const d = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
      stepBy(d > 0 ? 1 : -1);
    };

    useEffect(() => {
      const onKey = (e) => { if (e.key === "ArrowRight") stepBy(1); else if (e.key === "ArrowLeft") stepBy(-1); };
      window.addEventListener("keydown", onKey);
      return () => window.removeEventListener("keydown", onKey);
    }, [stepBy]);

    const clickTab = (i) => {
      if (drag.current.moved > 6) return;        // it was a revolve, not a tap
      if (i !== frontIndex) toFront(i);
      else if (onOpen) onOpen(tabs[i]);
    };

    const SPREAD_X = Math.min(dim.w * 0.42, 560);   // how far neighbours fan out along the line
    const RISE_Y = Math.max(28, Math.min(dim.h * 0.18, 52));  // shallow — keeps the wheel near a line

    return (
      <div className="ring-scene" ref={sceneRef}
           onPointerDown={onPointerDown} onPointerMove={onPointerMove}
           onPointerUp={endDrag} onPointerLeave={endDrag} onWheel={onWheel}>
        <div className={"ring" + (settling ? " settling" : "")}>
          {tabs.map((tab, i) => {
            const phi = norm180(i * step + rotation);
            const r = phi * Math.PI / 180;
            const off = Math.min(Math.abs(phi) / VISIBLE, 1);
            const hidden = Math.abs(phi) > VISIBLE;
            const x = Math.sin(r) * SPREAD_X;
            const y = -(1 - Math.cos(r)) * RISE_Y;     // front lowest, neighbours rise back toward the horizon
            const scale = 1 - 0.42 * off;
            const opacity = hidden ? 0 : 1 - 0.84 * off;
            const blur = off * 3.2;
            return (
              <div key={tab.slug}
                   className={"ring-tab" + (i === frontIndex ? " is-front" : "") + (tab.slug === risingSlug ? " rising" : "")}
                   style={{ transform: `translate(calc(-50% + ${x.toFixed(1)}px), calc(-50% + ${y.toFixed(1)}px)) scale(${scale.toFixed(3)})`,
                            opacity: opacity.toFixed(3), filter: blur > 0.2 ? `blur(${blur.toFixed(1)}px)` : "none",
                            zIndex: Math.round((Math.cos(r) + 1) * 50), pointerEvents: hidden ? "none" : "auto" }}
                   onClick={() => clickTab(i)}>
                <TabFace tab={tab} />
              </div>
            );
          })}
        </div>
        <div className="ring-hint"><span>drag</span><span>·</span><kbd>←</kbd><kbd>→</kbd><span>·</span><span>click to open</span></div>
      </div>
    );
  }

  window.Ring = Ring;
})();
