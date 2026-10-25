/* The phone throne room: its own tree, sharing EmpireData with the desktop.
   The server owns account visibility. No seed/admin fallback on an HTTP error. */
(function () {
  const { useState, useEffect, useRef } = React;
  const API = window.EmpireData;
  const newest = (entries) => entries.slice().sort((a, b) => b.at.localeCompare(a.at));
  const status = (province, admin) => !admin && province.state === "coming-soon" ? "COMING SOON" : province.status;

  // Render Lucide's icon data with React, without replacing React-owned DOM nodes.
  function Glyph({ name, size = 18 }) {
    const icon = window.lucide && window.lucide.icons[name];
    const nodes = icon && icon[2];
    return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {Array.isArray(nodes) && nodes.map(([tag, attrs], i) => React.createElement(tag, { ...attrs, key: i }))}
    </svg>;
  }

  function Mark({ province, crown = false }) {
    const [failed, setFailed] = useState(false);
    const name = province ? province.name : "Empire";
    return !failed && (crown || (province && province.logo))
      ? <img src={crown ? "brand/ares_transparent.webp" : province.logo} alt="" onError={() => setFailed(true)} />
      : <span className="em-monogram" aria-hidden="true">{name[0]}</span>;
  }

  function Timeline({ entries, projects, title }) {
    const logos = { aresium: "brand/hermes.webp", arestoteles: "brand/arestoteles_transparent.webp" };
    projects.forEach((p) => { if (!logos[p.slug] && p.logo) logos[p.slug] = p.logo; });
    return <section className="em-news" aria-label={title}>
      <div className="em-section-heading"><h2>{title}</h2></div>
      {entries.length ? <div className="em-timeline-wrap">
        <window.EmpireGoldDust vertical lineY={27} />
        <ol className="em-timeline">
        {newest(entries).map((entry, i) => <li className="log-node" key={entry.at + entry.project + i}>
          <span className="log-bust"><Mark province={{ name: entry.project || "Empire", logo: logos[entry.project] || "brand/ares_transparent.webp" }} /></span>
          <div className="log-meta"><time className="log-date" dateTime={entry.at}>{entry.at}</time><span className="log-dot">·</span><span className="log-proj">{entry.project || "empire"}</span></div>
          <p className="log-text">{entry.text}</p>
        </li>)}
        </ol>
      </div> : <p className="em-empty">No news yet.</p>}
    </section>;
  }

  // The desktop's own wheel (window.Ring): compact tabs, neighbours smaller, paler and blurred toward the sides.
  // Underneath, one quiet line about the province at the front. Ideas ride the same wheel when expanded.
  // Tap the front tab to open it, hold any tab for its page (as the Empire iPhone app does).
  function PhoneRing({ items, expanded, admin, onOpen, onHold, onAdd }) {
    const [front, setFront] = useState(null);
    const tabs = expanded ? items.map((idea) => ({ slug: idea.title, name: idea.title, status: "SCOUTED", idea }))
      : items.map((p) => (!admin && p.state === "coming-soon") ? { ...p, statusLabel: "COMING SOON" } : p);
    // Under the ring: the front province's live line, else what it is; nothing for ideas.
    const line = !front ? (onAdd ? "Add a province to your ring" : "") : expanded ? "" : (front.live || front.blurb || "");
    return <section className="em-ring" aria-label={expanded ? "Expansions" : "Provinces"}>
      <div className="em-ring-stage">
        <window.Ring key={expanded ? "ideas" : "provinces"} projects={tabs} onFront={setFront}
          onOpen={(tab) => onOpen(expanded ? tab.idea : tab)} onHold={(tab) => onHold(expanded ? tab.idea : tab)}
          addSlot={onAdd ? { label: "Add a province", onAdd } : undefined} />
      </div>
      <p className={"em-ring-line" + (front && front.live && !expanded ? " is-live" : "")} aria-live="polite">{line}</p>
    </section>;
  }

  function Dialog({ title, sheet, onClose, children, error }) {
    const ref = useRef(null);
    useEffect(() => {
      const previous = document.activeElement;
      ref.current.focus();
      const onKey = (event) => {
        if (event.key === "Escape") { event.preventDefault(); onClose(); }
        if (event.key !== "Tab") return;
        const focusable = Array.from(ref.current.querySelectorAll('button:not(:disabled), a[href], [tabindex="0"]'));
        const first = focusable[0], last = focusable[focusable.length - 1];
        if (event.shiftKey && (document.activeElement === first || document.activeElement === ref.current)) {
          event.preventDefault(); last && last.focus();
        } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === ref.current)) {
          event.preventDefault(); first && first.focus();
        }
      };
      document.addEventListener("keydown", onKey);
      return () => { document.removeEventListener("keydown", onKey); if (previous && previous.isConnected) previous.focus({ preventScroll: true }); };
    }, []);
    return <div className={"em-overlay" + (sheet ? " is-sheet" : "")} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <section className="em-dialog" ref={ref} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1}>
        {sheet && <div className="em-sheet-handle" aria-hidden="true" />}
        <header className="em-dialog-header"><span>{title}</span><button className="em-icon-button" aria-label="Close" title="Close" onClick={onClose}><Glyph name="X" /></button></header>
        <div className="em-dialog-content">{error && <p className="em-error" role="alert">{error}</p>}{children}</div>
      </section>
    </div>;
  }

  function Province({ province, data, onRemove, busy }) {
    const detail = province.detail || {};
    const comingSoon = !data.me.admin && province.state === "coming-soon";
    const destination = API.destination(province);
    // The mark and the name are the link (a small arrow says so); no separate Open button.
    const title = <React.Fragment><div className="em-detail-mark"><Mark province={province} /></div>
      <h1>{province.name}{destination && <span className="em-detail-arrow"><Glyph name="ArrowUpRight" size={15} /></span>}</h1></React.Fragment>;
    return <React.Fragment>
      <div className="em-detail-hero">
        {destination ? <a className="em-detail-link" href={destination} target="_blank" rel="noopener" aria-label={"Open " + province.name}>{title}</a> : title}
        <span className="em-status">{status(province, data.me.admin)}</span>
        <p className="em-detail-blurb">{province.blurb}</p>
        {province.live && <p className="em-detail-live">{province.live}</p>}
      </div>
      {comingSoon && <p className="em-coming-note">Coming soon. You’ll be able to open {province.name} here when it’s available.</p>}
      <section className="em-detail-section"><h2>About</h2><p>{detail.about || province.blurb}</p></section>
      <section className="em-detail-section"><h2>Features</h2>
        {detail.features && detail.features.length ? <ul>{detail.features.map((feature, i) => <li key={i}><Glyph name="Check" size={15} />{feature}</li>)}</ul> : <p>No features listed yet.</p>}
      </section>
      <Timeline title="What's new" entries={data.chronicle.filter((entry) => entry.project === province.slug)} projects={data.projects} />
      {!data.me.admin && <button className="em-remove" disabled={busy} onClick={() => onRemove(province.slug)}><Glyph name="Minus" size={16} />{busy ? "Removing…" : "Remove from my ring"}</button>}
    </React.Fragment>;
  }

  // The apps an account can ask for, by service (docs/ACCOUNTS.md → Accounts in every app).
  const APP_NAMES = { empire: "Ares Empire", aresium: "Aresium", arestemis: "Arestemis", aresus: "Aresus", arestoteles: "Arestoteles" };
  const appNames = (services) => (services || []).map((s) => APP_NAMES[s] || s).join(", ");

  // New sign-ups (approve lets them in) and approved accounts asking for more apps (approve grants them).
  function Approvals({ accounts, loading, busy, onDecide }) {
    const [declining, setDeclining] = useState(null);
    return <React.Fragment>
      {loading ? <p className="em-empty" role="status">Loading pending accounts…</p> : !accounts ? <p className="em-empty">Pending accounts could not be loaded.</p>
        : accounts.length ? <React.Fragment><div className="em-section-heading"><h2>Pending accounts</h2><span>{String(accounts.length).padStart(2, "0")}</span></div>
          <div className="em-accounts">{accounts.map((account) => <article className="em-account" key={account.id}>
            <div className="em-account-top"><span className="em-account-avatar">{(account.name || account.email)[0].toUpperCase()}</span><div><h2>{account.name || (account.approved ? "Account" : "New account")}</h2><p>{account.email}</p></div></div>
            <p className="em-account-date">{account.approved ? "Asks for more access" : <React.Fragment>Signed up <time dateTime={account.created}>{account.created.slice(0, 10)}</time></React.Fragment>}
              {account.requested && account.requested.length > 0 && <span>Asks for {appNames(account.requested)}</span>}</p>
            {declining === account.id ? <div className="em-decline-confirm" role="alert"><p>{account.approved
              ? "Decline " + (account.name || account.email) + "’s request? The account and its other apps stay."
              : "Decline " + (account.name || account.email) + "? This deletes their pending sign-up."}</p>
              <div className="em-actions"><button className="em-secondary" disabled={busy} onClick={() => setDeclining(null)}>Keep account</button>
                <button className="em-danger" disabled={busy} onClick={() => onDecide(account.id, { decline: true })}>Confirm decline</button></div></div>
              : <div className="em-actions"><button className="em-primary" disabled={busy} onClick={() => onDecide(account.id, { approve: true })}><Glyph name="Check" size={16} />Approve</button>
                <button className="em-secondary" disabled={busy} onClick={() => setDeclining(account.id)}>Decline</button></div>}
          </article>)}</div></React.Fragment> : <div className="em-empty-state"><Glyph name="Check" size={30} /><h2>No pending accounts.</h2></div>}
      {busy && <p className="em-empty" role="status">Updating account…</p>}
    </React.Fragment>;
  }

  function EmpireMobile() {
    const [data, setData] = useState(API.initial);
    const [loadError, setLoadError] = useState(null);
    const [retry, setRetry] = useState(0);
    const [expanded, setExpanded] = useState(false);
    const [modal, setModal] = useState(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState(null);
    const [notice, setNotice] = useState("");
    const [accounts, setAccounts] = useState(null);
    const [loadingAccounts, setLoadingAccounts] = useState(false);
    const alive = useRef(true);
    const locked = useRef(false);
    const close = () => { if (!locked.current) { setModal(null); setError(null); } };
    useEffect(() => {
      alive.current = true;
      let cancelled = false;
      setLoadError(null);
      API.load().then(API.validate).then((result) => { if (!cancelled) setData(result); })
        .catch((err) => { if (!cancelled) setLoadError(err.message || "The Empire could not load."); });
      return () => { cancelled = true; alive.current = false; };
    }, [retry]);

    const open = (next) => { setError(null); setModal(next); };
    // Tapping the front province opens it; one that cannot be opened (yet) shows its page instead.
    const launch = (province) => {
      const destination = API.destination(province);
      if (destination) window.open(destination, "_blank", "noopener");
      else open({ type: "province", item: province });
    };
    const ring = async (change) => {
      if (locked.current) return;
      locked.current = true; setBusy(true); setError(null);
      try {
        const result = await API.ring(change);
        if (alive.current) {
          setData(result); setModal(null);
          setNotice(change.add ? "Province added to your ring." : "Province removed from your ring.");
        }
      } catch (err) { if (alive.current) setError(err.message); }
      finally { locked.current = false; if (alive.current) setBusy(false); }
    };
    const approvals = async () => {
      open({ type: "approvals" }); setLoadingAccounts(true); setAccounts(null);
      try {
        const result = await API.approvals();
        if (alive.current) {
          setAccounts(result); setData((current) => ({ ...current, pending: result.length }));
        }
      } catch (err) { if (alive.current) setError(err.message); }
      finally { if (alive.current) setLoadingAccounts(false); }
    };
    const decide = async (id, decision) => {
      if (locked.current) return;
      locked.current = true; setBusy(true); setError(null);
      try {
        const account = (accounts || []).find((a) => a.id === id);
        await API.decide(id, decision);
        // Refresh the authoritative list (and count); the action has no body contract.
        const result = await API.approvals();
        if (alive.current) {
          setAccounts(result); setData((current) => ({ ...current, pending: result.length }));
          setNotice(account && account.approved ? (decision.approve ? "Access granted." : "Request declined.")
            : (decision.approve ? "Account approved." : "Sign-up declined."));
        }
      } catch (err) { if (alive.current) setError(err.message); }
      finally { locked.current = false; if (alive.current) setBusy(false); }
    };

    if (!data) return <main className="em-loading"><img src="brand/ares_transparent.webp" alt="" /><h1 className="gold-clip">THE EMPIRE</h1>
      {loadError ? <React.Fragment><p role="alert">{loadError}</p><button className="em-primary" onClick={() => setRetry(retry + 1)}>Try again</button><a className="em-secondary" href="/login">Log in</a></React.Fragment> : <p role="status">Loading…</p>}
    </main>;
    const admin = data.me.admin;
    const items = expanded && admin ? data.ideas : data.projects;
    return <div className="em-phone">
      <div className="em-backdrop" aria-hidden="true"><img src="brand/head_transparent_real.webp" alt="" /></div>
      <main className="em-home" inert={modal ? "" : undefined}>
        <header className="em-header">
          <img className="em-crest" src="brand/ares_transparent.webp" alt="" />
          <button className="em-title gold-clip" onClick={() => admin && setExpanded(!expanded)} aria-pressed={admin ? expanded : undefined}
            aria-label={admin ? (expanded ? "Show the provinces" : "Show the expansions") : "The Empire"}>
            {expanded ? "EXPANSIONS" : "THE EMPIRE"}</button>
          <div className="em-header-actions">
            {admin && <button className={"em-icon-button" + (expanded ? " is-active" : "")} aria-pressed={expanded}
              aria-label={expanded ? "Show the provinces" : "Show the expansions"} title={expanded ? "Provinces" : "Expansions"}
              onClick={() => setExpanded(!expanded)}><Glyph name={expanded ? "Orbit" : "Maximize2"} size={18} /></button>}
            {admin && <button className="em-icon-button em-inbox" aria-label={"Approvals, " + data.pending + " pending"} title="Approvals" onClick={approvals}>
              <Glyph name="Inbox" size={19} />{data.pending > 0 && <span className="em-count">{data.pending}</span>}</button>}
            <a className="em-icon-button" href={API.sampleMode ? "login.html" : "/logout"} aria-label="Log out" title="Log out"><Glyph name="LogOut" size={19} /></a>
          </div>
        </header>
        {items.length || !admin ? <PhoneRing key={(expanded ? "ideas" : "projects") + data.projects.map((p) => p.slug).join(",")}
          items={items} expanded={expanded} admin={admin}
          onOpen={(item) => expanded ? open({ type: "idea", item }) : launch(item)}
          onHold={(item) => open({ type: expanded ? "idea" : "province", item })}
          onAdd={admin ? null : () => open({ type: "add" })} />
          : <p className="em-empty">No expansions yet.</p>}
        {!expanded && <Timeline title={admin ? "Chronicle" : "What's new"} entries={data.chronicle} projects={data.projects} />}
        <footer className="em-home-footer">
          <window.LegalLinks className="em-legal" />
          {API.sampleMode && <span>{admin ? "Admin sample" : "Member sample"}</span>}
        </footer>
      </main>
      <span className="em-sr" role="status">{notice}</span>
      {modal && <Dialog title={({ province: "Provinces", idea: "Expansions", add: "Add a province", approvals: "Approvals" })[modal.type]}
        sheet={modal.type === "add"} onClose={close} error={error}>
        {modal.type === "province" && <Province province={modal.item} data={data} busy={busy} onRemove={(slug) => ring({ remove: slug })} />}
        {modal.type === "idea" && <React.Fragment><div className="em-detail-hero"><div className="em-detail-mark"><Glyph name="Layers" size={32} /></div><h1>{modal.item.title}</h1><span className="em-status">PLANNED</span></div><section className="em-detail-section"><h2>About</h2><p>{modal.item.note}</p></section></React.Fragment>}
        {modal.type === "add" && <React.Fragment>
          {data.addable.length ? <div className="em-catalog">{data.addable.map((p) => <article className="em-catalog-card" key={p.slug}>
            <div className="em-catalog-head"><div className="em-catalog-mark"><Mark province={p} /></div><div><h2>{p.name}</h2>{p.state === "coming-soon" && <span className="em-status">COMING SOON</span>}</div></div>
            <button className="em-primary" disabled={busy} onClick={() => ring({ add: p.slug })}><Glyph name="Plus" size={16} />{busy ? "Adding…" : "Add to my ring"}</button>
          </article>)}</div> : <div className="em-empty-state"><Glyph name="Check" size={28} /><h2>Your ring is up to date.</h2><p>No other provinces are available to add.</p></div>}
        </React.Fragment>}
        {modal.type === "approvals" && admin && <Approvals accounts={accounts} loading={loadingAccounts} busy={busy} onDecide={decide} />}
      </Dialog>}
    </div>;
  }
  window.EmpireMobile = EmpireMobile;
})();
