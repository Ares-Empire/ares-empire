/* Ares Empire — the orbital circle (window.Ring).

   The provinces ride a stretched ellipse, FACE-ON (a 2-D orbit, not a depth carousel),
   so even two of them read as "a circle of projects". The lower-centre slot is the focus;
   items higher on the ellipse recede (smaller, dimmer) for an orbit feel. Drag, scroll or
   ← / → to revolve. Click a back province to bring it forward; click the focused one to
   spread the whole circle into the project board.

   Props: { projects, onSpread(), risingSlug } */
(function () {
  const { useState, useRef, useEffect, useMemo, useCallback } = React;
  const SENS = 0.32;                 // degrees of revolve per pixel dragged
  const FRONT = 90;                  // the focus slot, in degrees (bottom-centre of the ellipse)
  const norm = (d) => ((d % 360) + 360) % 360;          // → [0,360)

  function statusClass(tone) {
    return { live: "st-live", wip: "st-wip", hold: "st-hold", scout: "st-scout" }[tone] || "st-scout";
  }

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

  function Ring({ projects, onSpread, risingSlug }) {
    const tabs = projects || [];
    const count = Math.max(tabs.length, 1);
    const step = 360 / count;

    const [rotation, setRotation] = useState(0);          // degrees; 0 → item 0 at the focus slot
    const [settling, setSettling] = useState(true);
    const drag = useRef({ on: false, startX: 0, startRot: 0, moved: 0 });
    const wheelAt = useRef(0);

    const measure = () => {
      const W = window.innerWidth, H = window.innerHeight;
      // wide & shallow — a stretched orbit that stays clear of the header/timeline
      return { rx: Math.min(W * 0.30, 460), ry: Math.min(H * 0.21, 188) };
    };
    const [dims, setDims] = useState(measure);
    useEffect(() => {
      const onR = () => setDims(measure());
      window.addEventListener("resize", onR);
      return () => window.removeEventListener("resize", onR);
    }, []);

    // focus = the item whose orbital angle is nearest the front slot
    const frontIndex = useMemo(() => {
      let best = 0, bestD = Infinity;
      for (let i = 0; i < count; i++) {
        const m = norm(i * step + rotation);              // 0 when item i is at the focus
        const d = Math.min(m, 360 - m);
        if (d < bestD) { bestD = d; best = i; }
      }
      return best;
    }, [rotation, count, step]);

    const stepBy = useCallback((n) => {
      const k = Math.round(rotation / step);
      setSettling(true); setRotation((k + n) * step);
    }, [rotation, step]);

    const toFront = useCallback((i) => {                  // shortest arc to put item i at the focus
      const target = -i * step;
      let delta = norm(target - rotation); if (delta > 180) delta -= 360;
      setSettling(true); setRotation(rotation + delta);
    }, [rotation, step]);

    // ---- revolve by dragging ----
    const onPointerDown = (e) => {
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
      const k = Math.round(rotation / step);              // snap to nearest province
      setSettling(true); setRotation(k * step);
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
        if (e.key === "ArrowRight") stepBy(1);
        else if (e.key === "ArrowLeft") stepBy(-1);
      };
      window.addEventListener("keydown", onKey);
      return () => window.removeEventListener("keydown", onKey);
    }, [stepBy]);

    const clickTab = (i) => {
      if (drag.current.moved > 6) return;                 // it was a revolve, not a tap
      if (i !== frontIndex) toFront(i);
      else if (onSpread) onSpread();
    };

    const { rx, ry } = dims;
    return (
      <div className="ring-scene"
           onPointerDown={onPointerDown} onPointerMove={onPointerMove}
           onPointerUp={endDrag} onPointerLeave={endDrag} onWheel={onWheel}>
        <div className="ring-shift">
          <div className="ring-orbit" style={{ "--orbit-w": (2 * rx + 70) + "px", "--orbit-h": (2 * ry + 64) + "px" }} />
          <div className={"ring" + (settling ? " settling" : "")}>
            {tabs.map((tab, i) => {
              const a = (FRONT + i * step + rotation) * Math.PI / 180;
              const x = rx * Math.cos(a), y = ry * Math.sin(a);
              const depth = (Math.sin(a) + 1) / 2;          // 1 at focus (front), 0 at the back
              const scale = 0.58 + 0.42 * depth;
              const opacity = 0.24 + 0.76 * depth;
              return (
                <div key={tab.slug}
                     className={"ring-tab" + (i === frontIndex ? " is-front" : "") + (tab.slug === risingSlug ? " rising" : "")}
                     style={{ transform: `translate(calc(-50% + ${x.toFixed(1)}px), calc(-50% + ${y.toFixed(1)}px)) scale(${scale.toFixed(3)})`,
                              opacity: opacity.toFixed(3), zIndex: Math.round(depth * 100) }}
                     onClick={() => clickTab(i)}>
                  <TabFace tab={tab} />
                </div>
              );
            })}
          </div>
        </div>
        <div className="ring-hint">
          <span>drag</span><span>·</span><kbd>←</kbd><kbd>→</kbd><span>·</span><span>click to open the board</span>
        </div>
      </div>
    );
  }

  window.Ring = Ring;
})();
