/* Ares Empire — brand marks (window.Bust, window.Wordmark, window.Icon).

   Bust renders the Ares crown bust (brand/ares-bust.png) with a marble placeholder that
   shows only if the file is missing. Wordmark renders ARES EMPIRE for the gold band / crown
   (the inter-word space becomes a wider slot so the two words read apart). Icon is a thin
   wrapper over Lucide so we don't hand-roll SVGs. */
(function () {
  const { useState } = React;

  const BUST_SRC = "brand/ares-bust.png";

  function MarblePlaceholder({ label }) {
    return (
      <div className="intro-bust-ph" aria-hidden="true" style={{ opacity: 1 }}>
        <div className="bust-ph-vein" />
        {label && <div className="bust-ph-cap">{label}</div>}
      </div>
    );
  }

  // square/portrait bust mark; fills its parent (set size on the wrapper via CSS)
  function Bust({ label = "ARES", className = "" }) {
    const [state, setState] = useState("probe"); // probe → real | ph
    return (
      <div className={"bust " + className} style={{ position: "relative", width: "100%", height: "100%" }}>
        {state !== "real" && (
          <img
            src={BUST_SRC} alt="Ares Empire"
            style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain", opacity: 0 }}
            onLoad={() => setState("real")} onError={() => setState("ph")}
          />
        )}
        {state === "real" && (
          <img src={BUST_SRC} alt="Ares Empire"
            style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain",
                     filter: "drop-shadow(0 14px 30px rgba(0,0,0,0.6))" }} />
        )}
        {state === "ph" && <MarblePlaceholder label={label} />}
      </div>
    );
  }

  // ARES EMPIRE in gold. `shimmer` adds the travelling glint.
  function Wordmark({ text = "ARES EMPIRE", className = "", shimmer = false }) {
    return (
      <div className={"ares-word " + (shimmer ? "shimmer " : "") + className} aria-hidden="true">
        {text.split("").map((ch, i) =>
          ch === " "
            ? <span key={i} style={{ minWidth: "0.5em" }}>&nbsp;</span>
            : <span key={i}>{ch}</span>
        )}
      </div>
    );
  }

  // Lucide icon helper → <Icon name="swords" />
  function Icon({ name, size = 18, stroke = 2, className = "" }) {
    const node = (window.lucide && window.lucide.icons && window.lucide.icons[
      name.replace(/(^|-)([a-z])/g, (_, d, c) => c.toUpperCase())
    ]) || null;
    // fall back to a data-driven <i> that lucide.createIcons() upgrades on mount
    return <i data-lucide={name} className={className} style={{ width: size, height: size, display: "inline-flex" }} />;
  }

  window.Bust = Bust;
  window.Wordmark = Wordmark;
  window.Icon = Icon;
})();
