/* Ares Empire — overlays (window.Oracle, window.WarCouncil, window.Chronicle, window.Forge).

   Oracle      — consult the Ares bust; it speaks a line + suggests a next conquest.
   WarCouncil  — the ideas scroll; promote one straight into the forge.
   Chronicle   — the changelog scroll Claude Code appends to ("did X to conquer Y").
   Forge       — CONQUER. Set a name + blurb; it generates the seed CLAUDE.md, the manifest
                 entry and the Claude Code handoff (copy buttons), then crowns the province
                 onto the ring (throne reveal). A browser can't touch your filesystem, so the
                 actual scaffold is done by Claude Code (or a future local /api/conquer). */
(function () {
  const { useState, useEffect, useRef, useMemo } = React;
  const E = () => window.EMPIRE || {};

  function useIcons(dep) { useEffect(() => { try { window.lucide && window.lucide.createIcons(); } catch (_) {} }); }
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
  const slugify = (s) => (s || "").toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

  // ---------------------------------------------------------------- Oracle
  function Oracle({ onClose, onCouncil }) {
    const lines = (E().oracle && E().oracle.length) ? E().oracle : ["Speak, and the empire listens."];
    const [line, setLine] = useState(() => pick(lines));
    const [shown, setShown] = useState("");
    const suggestion = useMemo(() => { const ids = E().ideas || []; return ids.length ? pick(ids) : null; }, [line]);
    useIcons();

    // typewriter
    useEffect(() => {
      setShown(""); let i = 0;
      const id = setInterval(() => { i++; setShown(line.slice(0, i)); if (i >= line.length) clearInterval(id); }, 26);
      return () => clearInterval(id);
    }, [line]);

    return (
      <div className="oracle" role="dialog" aria-modal="true" onClick={onClose}>
        <div className="oracle-card" onClick={(e) => e.stopPropagation()}>
          <div className="oracle-bust"><window.Bust label="ARES" /></div>
          <div className="oracle-k">THE ORACLE</div>
          <div className="oracle-text">{shown}<span style={{ opacity: shown.length < line.length ? 1 : 0 }}>▍</span></div>
          {suggestion && (
            <div className="oracle-suggest">
              The map has room. Consider taking <b>{suggestion.title}</b> — {suggestion.note}
            </div>
          )}
          <div className="oracle-actions">
            <button className="emp-btn-ghost" onClick={() => setLine(pick(lines.filter((l) => l !== line).concat(lines)))}>Consult again</button>
            <button className="emp-btn" onClick={onCouncil}>War Council</button>
          </div>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------- War Council (ideas)
  function WarCouncil({ onClose, onPromote }) {
    const ideas = E().ideas || [];
    useIcons();
    return (
      <React.Fragment>
        <div className="scrim" onClick={onClose} />
        <aside className="panel" role="dialog" aria-label="War Council">
          <div className="panel-head">
            <div>
              <div className="panel-k">WAR COUNCIL</div>
              <div className="panel-h">Future expansions</div>
            </div>
            <button className="panel-x" onClick={onClose} aria-label="Close"><window.Icon name="x" size={17} /></button>
          </div>
          <div className="panel-body">
            {ideas.length === 0 && <div className="chron-t">No campaigns drafted yet. Open CONQUER to begin one.</div>}
            {ideas.map((idea, i) => (
              <button key={i} className="idea" onClick={() => onPromote(idea)}>
                <div className="idea-t">{idea.title}<span className="go">CONQUER ›</span></div>
                <div className="idea-n">{idea.note}</div>
              </button>
            ))}
          </div>
        </aside>
      </React.Fragment>
    );
  }

  // ---------------------------------------------------------------- Chronicle (changelog)
  function Chronicle({ onClose }) {
    const log = E().chronicle || [];
    useIcons();
    return (
      <React.Fragment>
        <div className="scrim" onClick={onClose} />
        <aside className="panel" role="dialog" aria-label="The Chronicle">
          <div className="panel-head">
            <div>
              <div className="panel-k">THE CHRONICLE</div>
              <div className="panel-h">What was conquered</div>
            </div>
            <button className="panel-x" onClick={onClose} aria-label="Close"><window.Icon name="x" size={17} /></button>
          </div>
          <div className="panel-body">
            {log.map((c, i) => (
              <div key={i} className="chron">
                <div className="chron-meta"><span className="chron-proj">{(c.project || "empire").toUpperCase()}</span><span>{c.at}</span></div>
                <div className="chron-t">{c.text}</div>
              </div>
            ))}
          </div>
        </aside>
      </React.Fragment>
    );
  }

  // ---------------------------------------------------------------- Forge (CONQUER)
  function CopyBlock({ num, title, code }) {
    const [done, setDone] = useState(false);
    const copy = () => {
      try { navigator.clipboard.writeText(code).then(() => { setDone(true); setTimeout(() => setDone(false), 1600); }); }
      catch (_) {}
    };
    useIcons();
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

> Part of the **Ares Empire** (see ../../EMPIRE.md). Crown language: white marble · gold ·
> black; Space Grotesk + JetBrains Mono; glassmorphism; restrained motion. This province
> wears the empire's look but stays pure-white marble — sub-products are silver-on-black,
> the empire is gold-on-black.

## What this is
${blurb || "TODO — one line on what this province conquers."}

## State
BESIEGING — under active conquest.

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
    const [phase, setPhase] = useState("input"); // input → handoff
    const nameRef = useRef(null);
    useIcons();
    useEffect(() => { if (nameRef.current) nameRef.current.focus(); }, []);

    const slug = slugify(name);
    const claudeMd = seedClaudeMd(name || "New Province", slug || "new-province", blurb);
    const manifestEntry =
`{ slug: "${slug}", name: "${name}", url: "", logo: "brand/${slug}.png", status: "BESIEGING", domain: "", blurb: ${JSON.stringify(blurb)} },`;
    const handoff =
`claude "Conquer the province '${name}' for the Ares Empire: create projects/${slug}/ with the CLAUDE.md below, append its entry to web/app/empire-data.js (projects[]) and a dated line to the EMPIRE.md Chronicle, then 'git init' the province."`;

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
              <div className="forge-sub">Name the province. The empire will prepare its charter and the handoff to Claude Code.</div>
              <div className="forge-field">
                <label className="forge-label">PROVINCE NAME</label>
                <input ref={nameRef} className="forge-input" value={name} placeholder="e.g. Aresgora"
                       onChange={(e) => setName(e.target.value)}
                       onKeyDown={(e) => { if (e.key === "Enter" && name.trim()) setPhase("handoff"); }} />
                {slug && <div className="forge-hintline">directory <b>projects/{slug}/</b> · logo <b>brand/{slug}.png</b></div>}
              </div>
              <div className="forge-field">
                <label className="forge-label">WHAT IT CONQUERS <span style={{ color: "var(--ink-3)" }}>(one line)</span></label>
                <textarea className="forge-textarea" value={blurb} placeholder="A public agora — the empire's outward-facing landing."
                          onChange={(e) => setBlurb(e.target.value)} />
              </div>
              <div className="forge-actions">
                <button className="emp-btn-ghost" onClick={onClose}>Cancel</button>
                <button className="emp-btn" disabled={!name.trim()} style={{ opacity: name.trim() ? 1 : 0.5 }}
                        onClick={() => setPhase("handoff")}>Prepare the charter ›</button>
              </div>
            </React.Fragment>
          )}

          {phase === "handoff" && (
            <React.Fragment>
              <div className="forge-sub">
                Copy these into Claude Code to scaffold <b style={{ color: "var(--gold-hi)" }}>{name}</b>, then take the throne.
              </div>
              <div className="handoff">
                <CopyBlock num="1" title="The province's CLAUDE.md" code={claudeMd} />
                <CopyBlock num="2" title="Add to the manifest — web/app/empire-data.js → projects[]" code={manifestEntry} />
                <CopyBlock num="3" title="Hand off to Claude Code" code={handoff} />
              </div>
              <div className="forge-actions">
                <button className="emp-btn-ghost" onClick={() => setPhase("input")}>‹ Back</button>
                <button className="emp-btn" onClick={take}>Take the throne ⚔</button>
              </div>
            </React.Fragment>
          )}
        </div>
      </div>
    );
  }

  window.Oracle = Oracle;
  window.WarCouncil = WarCouncil;
  window.Chronicle = Chronicle;
  window.Forge = Forge;
})();
