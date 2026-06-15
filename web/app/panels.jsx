/* Ares Empire — the views (window.CardGrid, window.Timeline, window.Forge).

   CardGrid  — "project mode": the provinces (or the expansion plans) laid out on a clean,
               count-adaptive board (2 → L/R · 3 → L/M/R · 4 → quadrants · …) with context
               under each. Reused for PROJECTS (spread from the circle) and EXPANSIONS.
   Timeline  — the chronicle, as a horizontal ribbon below the circle.
   Forge     — CONQUER. Name a province; it generates the seed CLAUDE.md, the manifest entry
               and the Claude Code handoff, then crowns it onto the ring. (A browser can't
               touch the filesystem, so Claude Code does the actual scaffold.) */
(function () {
  const { useState, useEffect, useRef } = React;
  const E = () => window.EMPIRE || {};
  const useIcons = () => useEffect(() => { try { window.lucide && window.lucide.createIcons(); } catch (_) {} });
  const slugify = (s) => (s || "").toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  const statusClass = (tone) => ({ live: "st-live", wip: "st-wip", hold: "st-hold", scout: "st-scout" }[tone] || "st-scout");

  // columns per the requested patterns: 2→2 · 3→3 · 4→2×2 · then a balanced grid
  function columnsFor(n) {
    if (n <= 1) return 1;
    if (n <= 3) return n;
    if (n === 4) return 2;
    return Math.min(4, Math.ceil(Math.sqrt(n)));
  }

  function Mono({ name }) { return <div className="tab-mono">{(name || "?")[0]}</div>; }

  // ---------------------------------------------------------------- a project card
  function ProjectCard({ p, i, onVisit }) {
    const S = E().STATUS || {};
    const st = S[p.status] || null;
    const [imgErr, setImgErr] = useState(false);
    return (
      <button className="proj-card" style={{ animationDelay: i * 70 + "ms" }} onClick={() => onVisit(p)}>
        <div className="pc-top">
          <div className="pc-logo">
            {p.logo && !imgErr ? <img src={p.logo} alt={p.name} onError={() => setImgErr(true)} /> : <Mono name={p.name} />}
          </div>
          <div className="pc-id">
            <div className="pc-name">{p.name}</div>
            {st && <div className={"pc-status " + statusClass(st.tone)}>{st.label}</div>}
          </div>
        </div>
        <div className="pc-blurb">{p.blurb}</div>
        <div className="pc-foot">
          <span className="pc-domain">{p.domain || (p.url || "").replace(/^https?:\/\//, "") || "—"}</span>
          {p.url && <span className="pc-visit">Visit<window.Icon name="arrow-up-right" size={13} /></span>}
        </div>
      </button>
    );
  }

  // ---------------------------------------------------------------- an expansion (plan) card
  function ExpansionCard({ idea, i, onForge }) {
    return (
      <button className="proj-card" style={{ animationDelay: i * 70 + "ms" }} onClick={() => onForge(idea)}>
        <div className="pc-top">
          <div className="pc-logo"><Mono name={idea.title} /></div>
          <div className="pc-id">
            <div className="pc-name">{idea.title}</div>
            <div className="pc-status st-scout">PLANNED</div>
          </div>
        </div>
        <div className="pc-blurb">{idea.note}</div>
        <div className="pc-foot">
          <span className="pc-domain">expansion</span>
          <span className="pc-visit">Conquer<window.Icon name="chevron-right" size={13} /></span>
        </div>
      </button>
    );
  }

  function NewCard({ i, onForge }) {
    return (
      <button className="proj-card is-new" style={{ animationDelay: i * 70 + "ms" }} onClick={() => onForge(null)}>
        <div className="pc-new-mark"><window.Icon name="plus" size={24} /></div>
        <div className="pc-name">Claim new ground</div>
        <div className="pc-blurb" style={{ flex: "none", textAlign: "center", marginTop: 8 }}>Forge a fresh province from scratch.</div>
      </button>
    );
  }

  function CardGrid({ items, kind, onBack, onVisit, onForge }) {
    useIcons();
    const list = items || [];
    const total = list.length + (kind === "expansion" ? 1 : 0);
    const cols = columnsFor(total);
    return (
      <div className="grid-wrap">
        {kind === "project" && (
          <div className="grid-bar">
            <button className="grid-back" onClick={onBack}><window.Icon name="orbit" size={14} />Back to the circle</button>
          </div>
        )}
        <div className="card-grid" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
          {list.map((it, i) => kind === "project"
            ? <ProjectCard key={it.slug || i} p={it} i={i} onVisit={onVisit} />
            : <ExpansionCard key={i} idea={it} i={i} onForge={onForge} />)}
          {kind === "expansion" && <NewCard i={list.length} onForge={onForge} />}
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------- the timeline (chronicle)
  function Timeline({ log }) {
    if (!log || !log.length) return null;
    return (
      <div className="emp-timeline">
        <div className="tl-rail">
          {log.map((c, i) => (
            <div className="tl-item" key={i}>
              <span className="tl-node" />
              <div className="tl-meta">
                <span className="tl-proj">{c.project || "empire"}</span>
                <span className="tl-date">{c.at}</span>
              </div>
              <div className="tl-text">{c.text}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------- the Forge (CONQUER)
  function CopyBlock({ num, title, code }) {
    const [done, setDone] = useState(false);
    useIcons();
    const copy = () => {
      try { navigator.clipboard.writeText(code).then(() => { setDone(true); setTimeout(() => setDone(false), 1600); }); } catch (_) {}
    };
    return (
      <div className="handoff-step">
        <div className="handoff-num">STEP {num}</div>
        <div className="handoff-h">{title}</div>
        <div className="codeblock">
          <button className={"copy-btn" + (done ? " done" : "")} onClick={copy}>
            <window.Icon name={done ? "check" : "copy"} size={13} />{done ? "Copied" : "Copy"}
          </button>
          <pre>{code}</pre>
        </div>
      </div>
    );
  }

  function seedClaudeMd(name, slug, blurb) {
    return `# ${name} — an Ares Empire province

> Part of the **Ares Empire** (see ../../EMPIRE.md). House language: near-black wall ·
> polished-gold accents · Space Grotesk + JetBrains Mono · glassmorphism · restrained motion.

## What this is
${blurb || "TODO — one line on what this province does."}

## State
BESIEGING — under active build.

## How it joins the empire
- Registered in the manifest as \`${slug}\` (web/app/empire-data.js → projects[]).
- When it goes live: status → CONQUERED, add a domain + a logo at brand/${slug}.png.
- Append a line to the EMPIRE.md Chronicle whenever you do meaningful work here.

## Notes
TODO — stack, deploy, domain.
`;
  }

  function Forge({ initial, onClose, onConquered }) {
    const [name, setName] = useState((initial && initial.title) || "");
    const [blurb, setBlurb] = useState((initial && initial.note) || "");
    const [phase, setPhase] = useState("input");      // input → handoff
    const nameRef = useRef(null);
    useIcons();
    useEffect(() => { if (nameRef.current) nameRef.current.focus(); }, []);

    const slug = slugify(name);
    const claudeMd = seedClaudeMd(name || "New Province", slug || "new-province", blurb);
    const manifestEntry =
      `{ slug: "${slug}", name: "${name}", url: "", logo: "brand/${slug}.png", status: "BESIEGING", domain: "", blurb: ${JSON.stringify(blurb)} },`;
    const handoff =
      `claude "Build the province '${name}' for the Ares Empire: create projects/${slug}/ with the CLAUDE.md below, append its entry to web/app/empire-data.js (projects[]) and a dated line to the EMPIRE.md Chronicle, then 'git init' the province."`;

    const take = () => {
      onConquered && onConquered({
        slug: slug || "new-province", name: name || "New Province",
        url: "", logo: "brand/" + (slug || "new-province") + ".png",
        status: "BESIEGING", domain: "", blurb,
      });
    };

    return (
      <div className="forge" role="dialog" aria-modal="true" onClick={onClose}>
        <div className="forge-card" onClick={(e) => e.stopPropagation()}>
          <button className="panel-x" style={{ position: "absolute", top: 16, right: 16 }} onClick={onClose} aria-label="Close">
            <window.Icon name="x" size={17} />
          </button>
          <div className="forge-k">CONQUER</div>
          <div className="forge-h">Claim new ground</div>

          {phase === "input" && (
            <React.Fragment>
              <div className="forge-sub">Name the province. The empire prepares its charter and the handoff to Claude Code.</div>
              <div className="forge-field">
                <label className="forge-label">Province name</label>
                <input ref={nameRef} className="forge-input" value={name} placeholder="e.g. Aresgora"
                       onChange={(e) => setName(e.target.value)}
                       onKeyDown={(e) => { if (e.key === "Enter" && name.trim()) setPhase("handoff"); }} />
                {slug && <div className="forge-hintline">directory <b>projects/{slug}/</b> · logo <b>brand/{slug}.png</b></div>}
              </div>
              <div className="forge-field">
                <label className="forge-label">What it does <span style={{ color: "var(--ink-3)", letterSpacing: "0.02em", textTransform: "none" }}>(one line)</span></label>
                <textarea className="forge-textarea" value={blurb} placeholder="A public agora — the empire's outward-facing landing."
                          onChange={(e) => setBlurb(e.target.value)} />
              </div>
              <div className="forge-actions">
                <button className="emp-btn-ghost" onClick={onClose}>Cancel</button>
                <button className="emp-btn" disabled={!name.trim()} onClick={() => setPhase("handoff")}>Prepare the charter ›</button>
              </div>
            </React.Fragment>
          )}

          {phase === "handoff" && (
            <React.Fragment>
              <div className="forge-sub">Copy these into Claude Code to scaffold <b style={{ color: "var(--gold-hi)" }}>{name}</b>, then add it to the circle.</div>
              <CopyBlock num="1" title="The province's CLAUDE.md" code={claudeMd} />
              <CopyBlock num="2" title="Add to the manifest — web/app/empire-data.js → projects[]" code={manifestEntry} />
              <CopyBlock num="3" title="Hand off to Claude Code" code={handoff} />
              <div className="forge-actions">
                <button className="emp-btn-ghost" onClick={() => setPhase("input")}>‹ Back</button>
                <button className="emp-btn" onClick={take}>Add to the circle</button>
              </div>
            </React.Fragment>
          )}
        </div>
      </div>
    );
  }

  window.CardGrid = CardGrid;
  window.Timeline = Timeline;
  window.Forge = Forge;
})();
