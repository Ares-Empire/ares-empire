/* Ares Empire — intro module (window.EmpireIntro). SELF-CONTAINED.

   Forks the Arestoteles intro *technique* (a self-built fullscreen overlay animated with the
   Web Animations API; cracks drawn as SVG stroke-dashoffset) but in the CROWN treatment: the
   Ares bust falls in DEPTH onto the black wall, SLAMS, and the fissures it throws run RADIANT
   MOLTEN GOLD (bright gold core + amber bloom, styled in styles.css) with a warm gold flash and
   dust. Then "ARES EMPIRE" SLAMS in, letter by letter, in gold. The whole overlay then
   crossfades — it MORPHS straight into the hub (the wordmark does not travel to the top; the
   throne room simply dissolves in underneath).

   play({ onDone, onReveal, reducedOk })
     onReveal  fires as the crossfade begins → reveal the live hub UNDER the opaque overlay
     onDone    called once the overlay is torn down
     reducedOk if true, honor prefers-reduced-motion by skipping straight to onReveal/onDone

   Tunables live in CFG. Honors prefers-reduced-motion. */
(function () {
  "use strict";

  const BUST_SRC = "brand/ares-bust.png";
  const WORD = "ARES EMPIRE";
  let prefersReduced = false;
  try { prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (_) {}

  // one crown treatment — a hard, cinematic slam (gold as accent, not glare)
  const CFG = {
    total: 3400, fallMs: 860, fallEase: "cubic-bezier(.45,.05,.6,1)",
    startScale: 2.8, startCenter: 0.30, restCenter: 0.50,
    shake: 18, crackN: 14, flash: 0.5, dust: 1.0,
  };

  function el(tag, cls, css) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (css) Object.assign(e.style, css);
    return e;
  }

  // the bust DOM — real PNG, marble placeholder shown ONLY if it fails to load (no card flash)
  function buildBust() {
    const wrap = el("div", "intro-bust");
    const ph = el("div", "intro-bust-ph"); ph.style.opacity = "0";
    ph.appendChild(el("div", "bust-ph-vein"));
    const cap = el("div", "bust-ph-cap"); cap.textContent = "ARES"; ph.appendChild(cap);
    const img = el("img", "intro-bust-img"); img.alt = "Ares Empire"; img.style.opacity = "0";
    img.onload = () => { img.style.opacity = "1"; ph.style.opacity = "0"; };
    img.onerror = () => { img.remove(); ph.style.opacity = "1"; };
    img.src = BUST_SRC;
    if (img.complete && img.naturalWidth) img.style.opacity = "1";
    wrap.appendChild(ph); wrap.appendChild(img);
    return wrap;
  }

  function run(cfg, onDone, onReveal) {
    const root = document.body;
    const overlay = el("div", "intro-overlay");
    const shake = el("div", "intro-shake");
    const stage = el("div", "intro-stage");

    const W = window.innerWidth, H = window.innerHeight;
    const bustH = 0.44 * H, bustW = bustH * 0.785, halfH = bustH / 2;
    const cxPx = W / 2;
    const restCenterPx = cfg.restCenter * H;
    const craterCenterY = restCenterPx + halfH * 0.34;
    const impactY = restCenterPx + halfH * 0.52;
    const craterD = bustW * 3.4;

    // crater — a shallow scorched depression under the bust footprint
    const crater = el("div", "intro-crater");
    Object.assign(crater.style, {
      position: "absolute", left: cxPx + "px", top: craterCenterY + "px",
      width: craterD + "px", height: craterD * 0.9 + "px", transform: "translate(-50%,-50%)",
    });

    // molten cracks — a radial network bursting out of the bust's lower silhouette
    const SVGNS = "http://www.w3.org/2000/svg";
    const crackSvg = document.createElementNS(SVGNS, "svg");
    crackSvg.setAttribute("class", "intro-cracks");
    crackSvg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const crackPaths = [];
    const ox = cxPx, oy = craterCenterY;
    // a TIGHT root so every fissure springs from one point (then grows outward, all at once)
    const rx = bustW * 0.15, ry = bustH * 0.09, base = bustW, intensity = cfg.crackN;

    function jaggedOut(sx, sy, ang, L, segs, jitter) {
      let d = `M ${sx.toFixed(1)} ${sy.toFixed(1)}`;
      let x = sx, y = sy; const pts = [{ x, y }];
      for (let i = 1; i <= segs; i++) {
        const t = i / segs;
        const step = (L / segs) * (0.7 + Math.random() * 0.6);
        const a = ang + (Math.random() - 0.5) * jitter * (0.5 + t);
        x += Math.cos(a) * step; y += Math.sin(a) * step;
        d += ` L ${x.toFixed(1)} ${y.toFixed(1)}`; pts.push({ x, y });
      }
      return { d, pts };
    }
    function addPath(d, w, core) {
      const p = document.createElementNS(SVGNS, "path");
      p.setAttribute("d", d);
      p.setAttribute("class", core ? "intro-crack core" : "intro-crack");
      p.setAttribute("stroke-width", w.toFixed(2));
      crackSvg.appendChild(p); crackPaths.push(p);
    }

    for (let i = 0; i < intensity; i++) {
      const ang = (Math.PI * 2 * i) / intensity + (Math.random() - 0.5) * (Math.PI / intensity) * 1.6;
      const sx = ox + Math.cos(ang) * rx, sy = oy + Math.sin(ang) * ry;
      const reach = 0.5 + Math.random() * 0.8;
      const L = reach * base * 1.35;
      const segs = 5 + Math.floor(Math.random() * 4);
      const w = 1.1 + Math.random() * 1.1;     // fine — gold as a thread, not a tendril
      const main = jaggedOut(sx, sy, ang, L, segs, 0.7);
      addPath(main.d, w, false);               // a fine gold fissure (no molten-core glare)
      const nb = Math.floor(Math.random() * 2);  // 0–1 hairline branches
      for (let b = 0; b < nb; b++) {
        const k = 2 + Math.floor(Math.random() * (main.pts.length - 3));
        const bp = main.pts[k];
        const ba = ang + (Math.random() < 0.5 ? -1 : 1) * (0.35 + Math.random() * 0.55);
        const bl = L * (0.3 + Math.random() * 0.4);
        const br = jaggedOut(bp.x, bp.y, ba, bl, 3 + Math.floor(Math.random() * 3), 0.85);
        addPath(br.d, Math.max(0.8, w * (0.42 + Math.random() * 0.22)), false);
      }
    }

    // dust puffs kicked up by the impact
    const dusts = [];
    const dn = Math.round(8 * cfg.dust);
    for (let i = 0; i < dn; i++) {
      const d = el("div", "intro-dust", {
        left: (cxPx + (Math.random() - 0.5) * bustH * 0.95) + "px",
        top: (impactY - Math.random() * 22) + "px",
        width: (bustH * (0.18 + Math.random() * 0.3)) + "px",
        height: (bustH * (0.18 + Math.random() * 0.3)) + "px",
      });
      dusts.push(d);
    }

    const flash = el("div", "intro-flash");

    const bust = buildBust();
    bust.style.height = bustH + "px"; bust.style.left = cxPx + "px"; bust.style.top = "0px";

    // wordmark band — ARES EMPIRE (space rendered as a wider slot so the two words read apart)
    const band = el("div", "intro-band");
    const word = el("div", "ares-word intro-word");
    WORD.split("").forEach((ch) => {
      const s = el("span");
      if (ch === " ") { s.innerHTML = "&nbsp;"; s.style.minWidth = "0.5em"; }
      else s.textContent = ch;
      word.appendChild(s);
    });
    band.appendChild(word);

    // z-order: crater · cracks on the WALL (behind bust); bust lands into them; dust + flash in FRONT
    stage.appendChild(crater);
    stage.appendChild(crackSvg);
    stage.appendChild(bust);
    dusts.forEach((d) => stage.appendChild(d));
    stage.appendChild(flash);
    stage.appendChild(band);
    shake.appendChild(stage); overlay.appendChild(shake); root.appendChild(overlay);

    // geometry: transform-origin center; translateY positions the box CENTER at a screen fraction
    const tY = (cf) => (cf * H - halfH);
    const tf = (cf, s) => `translate(-50%, ${tY(cf).toFixed(1)}px) scale(${s})`;
    const fall = cfg.fallMs;

    // 1) bust falls in depth
    bust.animate([
      { transform: tf(cfg.startCenter, cfg.startScale), filter: "blur(1.5px)" },
      { transform: tf(cfg.restCenter, 1), filter: "blur(0px)", offset: 1 },
    ], { duration: fall, easing: cfg.fallEase, fill: "both" });

    // settle micro-bounce
    setTimeout(() => {
      bust.animate([
        { transform: tf(cfg.restCenter, 1) },
        { transform: `translate(-50%, ${(tY(cfg.restCenter) + 6).toFixed(1)}px) scale(1.012,.985)`, offset: 0.35 },
        { transform: tf(cfg.restCenter, 1) },
      ], { duration: 440, easing: "cubic-bezier(.34,1.56,.5,1)", fill: "both" });
    }, fall);

    // 2) screen shake
    if (cfg.shake > 0) setTimeout(() => {
      const S = cfg.shake, kf = [], steps = 9;
      for (let i = 0; i <= steps; i++) {
        const d = 1 - i / steps;
        kf.push({ transform: `translate(${(Math.random() - 0.5) * 2 * S * d}px, ${(Math.random() - 0.5) * 2 * S * d}px)` });
      }
      kf.push({ transform: "translate(0,0)" });
      shake.animate(kf, { duration: 470, easing: "ease-out", fill: "both" });
    }, fall);

    // 3) crater opens on impact
    crater.animate([
      { opacity: 0, transform: "translate(-50%,-50%) scale(.78)" },
      { opacity: 1, transform: "translate(-50%,-50%) scale(1.05)", offset: 0.35 },
      { opacity: 1, transform: "translate(-50%,-50%) scale(1)" },
    ], { duration: 640, delay: fall, easing: "cubic-bezier(.18,.9,.3,1)", fill: "both" });

    // 4) cracks draw outward — ALL at once from the root (no clockwise stagger), then grow
    crackPaths.forEach((p) => {
      const len = p.getTotalLength();
      p.style.strokeDasharray = len; p.style.strokeDashoffset = len;
      p.animate([{ strokeDashoffset: len }, { strokeDashoffset: 0 }],
        { duration: 720 + Math.random() * 360, delay: fall + Math.random() * 50, easing: "cubic-bezier(.2,.7,.2,1)", fill: "both" });
    });

    // 5) dust
    dusts.forEach((d) => {
      d.animate([
        { opacity: 0, transform: "translate(-50%,-50%) scale(.3) translateY(0)" },
        { opacity: 0.55, offset: 0.2 },
        { opacity: 0, transform: `translate(-50%,-50%) scale(1.9) translateY(-${44 + Math.random() * 60}px)` },
      ], { duration: 1150 + Math.random() * 480, delay: fall - 30, easing: "cubic-bezier(.2,.6,.3,1)", fill: "both" });
    });

    // 6) warm gold flash at the moment of impact
    flash.animate([{ opacity: 0 }, { opacity: cfg.flash, offset: 0.1 }, { opacity: 0 }],
      { duration: 460, delay: fall - 20, easing: "ease-out", fill: "both" });

    // 7) ARES EMPIRE SLAMS in — near-simultaneous (like the bust), with a single gold shine
    const wordIn = fall + 300;
    band.style.opacity = "1";
    const spans = word.querySelectorAll("span");
    spans.forEach((s, i) => {
      s.animate([
        { opacity: 0, transform: "translateY(48px) scale(.85)", filter: "blur(3px)" },
        { opacity: 1, transform: "translateY(-6px) scale(1.02)", filter: "blur(0)", offset: 0.55 },
        { opacity: 1, transform: "translateY(2px)", offset: 0.78 },
        { opacity: 1, transform: "translateY(0) scale(1)" },
      ], { duration: 470, delay: wordIn + i * 12, easing: "cubic-bezier(.26,1.42,.42,1)", fill: "both" });
    });
    // the specular sweep crosses the gold once, as the letters settle
    setTimeout(() => { word.classList.add("shine"); }, wordIn + 300);

    // 8) finish → morph (crossfade) into the hub
    const forceFinal = () => {
      [bust, shake, crater, flash, ...dusts, ...crackPaths, ...spans].forEach((n) => {
        if (n) n.getAnimations().forEach((a) => a.cancel());
      });
      bust.style.transform = tf(cfg.restCenter, 1); bust.style.filter = "none";
      shake.style.transform = "none"; band.style.opacity = "1";
      spans.forEach((s) => { s.style.opacity = "1"; s.style.transform = "none"; });
      crater.style.opacity = "1"; crater.style.transform = "translate(-50%,-50%) scale(1)";
      crackPaths.forEach((p) => { p.style.strokeDashoffset = "0"; });
      dusts.forEach((d) => { d.style.opacity = "0"; }); flash.style.opacity = "0";
    };
    const cleanup = () => { if (overlay.parentNode) overlay.parentNode.removeChild(overlay); if (onDone) onDone(); };
    setTimeout(() => {
      forceFinal();
      if (onReveal) { try { onReveal(); } catch (_) {} }   // reveal hub UNDER the still-opaque overlay
      overlay.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 560, easing: "ease", fill: "both" })
        .finished.then(cleanup).catch(cleanup);
    }, cfg.total - 560);
  }

  window.EmpireIntro = {
    play(opts) {
      opts = opts || {};
      if (opts.reducedOk && prefersReduced) { if (opts.onReveal) opts.onReveal(); if (opts.onDone) opts.onDone(); return; }
      let started = false;
      const go = () => { if (started) return; started = true; run(CFG, opts.onDone, opts.onReveal); };
      const im = new Image(); im.onload = go; im.onerror = go; im.src = BUST_SRC;
      if (im.complete) go(); else setTimeout(go, 360);
    },
  };
})();
