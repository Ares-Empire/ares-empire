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

  // The orbit the provinces revolve on is invisible (the old rim line was removed). RingDust
  // traces it with the same warm-gold dust as the chronicle timeline — a soft halo, no line,
  // no markers. The ellipse mirrors the Ring's own geometry (centre a touch above the front row).
  function RingDust() {
    const ref = useRef(null);
    useEffect(() => {
      const canvas = ref.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      let w = 0, h = 0, raf = 0;
      const parts = [];

      function resize() {
        const r = canvas.getBoundingClientRect();
        w = Math.max(1, r.width); h = Math.max(1, r.height);
        canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      }
      resize();
      const ro = new ResizeObserver(resize); ro.observe(canvas);

      // ellipse matching the wheel: rx/ry mirror Ring's SPREAD_X/RISE_Y; centre sits one
      // RISE_Y above the front-row baseline (top:68% in CSS), per the wheel's parametrics.
      function geom() {
        const rx = Math.min(w * 0.42, 560);
        const ry = Math.max(28, Math.min(h * 0.18, 52));
        return { rx, ry, cx: w * 0.5, cy: h * 0.68 - ry };
      }
      // same warm-gold tint the timeline dust uses
      function dot(x, y, a, warm, size) {
        ctx.globalAlpha = a;
        ctx.fillStyle = "rgb(255," + (212 - (warm * 36 | 0)) + "," + (120 + (warm * 70 | 0)) + ")";
        ctx.beginPath(); ctx.arc(x, y, Math.max(0.2, size), 0, 6.2832); ctx.fill();
      }

      function frame() {
        ctx.clearRect(0, 0, w, h);
        ctx.globalCompositeOperation = "lighter";
        const g = geom();
        if (!reduce) {
          const peri = Math.PI * (g.rx + g.ry);
          const n = Math.max(3, Math.round(peri / 260));
          for (let k = 0; k < n; k++) {
            const th = Math.random() * 6.2832;
            const nx = Math.cos(th), ny = Math.sin(th);             // ~outward normal of the rim
            parts.push({ x: g.cx + nx * g.rx + (Math.random() * 2 - 1) * 1.5,
                         y: g.cy + ny * g.ry + (Math.random() * 2 - 1) * 1.5,
                         vx: nx * 0.12 + (Math.random() - 0.5) * 0.18,
                         vy: ny * 0.10 - (0.05 + Math.random() * 0.18),  // a gentle lift, like the timeline
                         life: 1, size: 0.6 + Math.random() * 1.7, warm: Math.random() });
          }
          for (let i = parts.length - 1; i >= 0; i--) {
            const p = parts[i];
            p.x += p.vx; p.y += p.vy; p.vx *= 0.99; p.vy *= 0.99; p.life -= 0.012;
            if (p.life <= 0) { parts.splice(i, 1); continue; }
            const a = p.life * p.life;
            dot(p.x, p.y, a * 0.9, p.warm, p.size * a);
          }
        } else {
          // reduced motion: a static golden sprinkle around the orbit
          for (let i = 0; i < 64; i++) {
            const th = (i / 64) * 6.2832;
            dot(g.cx + Math.cos(th) * g.rx, g.cy + Math.sin(th) * g.ry, 0.45, (i % 5) / 5, 1.0);
          }
        }
        ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over";
        raf = requestAnimationFrame(frame);
      }
      raf = requestAnimationFrame(frame);
      return () => { cancelAnimationFrame(raf); ro.disconnect(); };
    }, []);
    return <canvas ref={ref} className="ring-dust" aria-hidden="true" />;
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
        <RingDust />
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
