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
  function ProjectCard({ p, i, onOpen }) {
    const S = E().STATUS || {};
    const st = S[p.status] || null;
    const [imgErr, setImgErr] = useState(false);
    return (
      <button className="proj-card" style={{ animationDelay: i * 70 + "ms" }}
              onClick={(e) => onOpen(p, e.currentTarget.getBoundingClientRect())}>
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
          <span className="pc-visit">Details<window.Icon name="maximize-2" size={13} /></span>
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

  function CardGrid({ items, kind, onBack, onOpen, onForge }) {
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
            ? <ProjectCard key={it.slug || i} p={it} i={i} onOpen={onOpen} />
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

  // ---------------------------------------------------------------- the province page (detail)
  // A board card morphs to a full-screen page: its rect animates to fill the viewport, then the
  // content fades in. Sections degrade to a tidy empty state for anything not yet written.
  function pdEmpty(text) { return <div className="pd-empty">{text}</div>; }

  function PdList({ items, empty }) {
    if (!items || !items.length) return pdEmpty(empty);
    return <ul className="pd-list">{items.map((t, i) => <li key={i}>{t}</li>)}</ul>;
  }

  function PdSection({ icon, title, wide, children }) {
    return (
      <div className={"pd-section" + (wide ? " wide" : "")}>
        <div className="pd-sec-h"><window.Icon name={icon} size={14} /><span>{title}</span></div>
        <div className="pd-sec-body">{children}</div>
      </div>
    );
  }

  function ProjectDetail({ project, originRect, onClose, onVisit }) {
    const p = project || {};
    const d = p.detail || {};
    const st = (E().STATUS || {})[p.status] || null;
    const [imgErr, setImgErr] = useState(false);
    const [open, setOpen] = useState(false);
    const full = () => ({ top: 0, left: 0, width: window.innerWidth, height: window.innerHeight, radius: 0 });
    const fromCard = () => originRect
      ? { top: originRect.top, left: originRect.left, width: originRect.width, height: originRect.height, radius: 16 }
      : full();
    const [box, setBox] = useState(fromCard);
    useIcons();

    const close = () => { setOpen(false); setBox(fromCard()); setTimeout(onClose, 380); };

    useEffect(() => {
      // two rAFs so the initial (card-sized) box paints before we animate it to full screen
      const id = requestAnimationFrame(() => requestAnimationFrame(() => { setBox(full()); setOpen(true); }));
      const onKey = (e) => { if (e.key === "Escape") close(); };
      window.addEventListener("keydown", onKey);
      return () => { cancelAnimationFrame(id); window.removeEventListener("keydown", onKey); };
    }, []);

    // change log: the province's own, else the empire chronicle entries tagged with its slug
    const log = (d.changelog && d.changelog.length)
      ? d.changelog
      : (E().chronicle || []).filter((c) => c.project === p.slug);

    return (
      <div className="pd-scrim" onClick={close}>
        <div className={"pd-panel" + (open ? " open" : "")} onClick={(e) => e.stopPropagation()}
             style={{ top: box.top, left: box.left, width: box.width, height: box.height, borderRadius: box.radius }}>
          <button className="pd-close" onClick={close} aria-label="Close"><window.Icon name="x" size={18} /></button>
          <div className="pd-inner">
            <header className="pd-head">
              <div className="pd-logo">
                {p.logo && !imgErr
                  ? <img src={p.logo} alt={p.name} onError={() => setImgErr(true)} />
                  : <div className="tab-mono">{(p.name || "?")[0]}</div>}
              </div>
              <div className="pd-id">
                <button className="pd-name" onClick={() => onVisit(p)} title={"Open " + (p.domain || p.name || "the site")}>
                  <span className="pd-name-t">{p.name}</span><window.Icon name="arrow-up-right" size={22} />
                </button>
                <div className="pd-sub">
                  {st && <span className={"pc-status " + statusClass(st.tone)}>{st.label}</span>}
                  {p.domain && <span className="pd-domain">{p.domain}</span>}
                </div>
              </div>
            </header>

            <div className="pd-grid">
              <PdSection icon="scroll-text" title="Overview" wide>
                <p className="pd-p">{d.about || p.blurb || "—"}</p>
                {d.features && d.features.length ? (
                  <React.Fragment>
                    <div className="pd-subh">Features</div>
                    <PdList items={d.features} />
                  </React.Fragment>
                ) : null}
              </PdSection>

              <PdSection icon="terminal" title="Setup">
                {d.setup ? <p className="pd-p">{d.setup}</p> : pdEmpty("No setup notes yet.")}
              </PdSection>
              <PdSection icon="loader" title="In progress · pending">
                <PdList items={d.wip} empty="No open items." />
              </PdSection>
              <PdSection icon="lightbulb" title="Add-ons · ideas">
                <PdList items={d.ideas} empty="No ideas captured yet." />
              </PdSection>

              <PdSection icon="history" title="Change log" wide>
                {log && log.length ? (
                  <ul className="pd-log">
                    {log.map((c, i) => (
                      <li key={i}><span className="pd-log-date">{c.at}</span><span>{c.text}</span></li>
                    ))}
                  </ul>
                ) : pdEmpty("No entries yet.")}
              </PdSection>
            </div>
          </div>
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
  window.ProjectDetail = ProjectDetail;
  window.Forge = Forge;
})();
