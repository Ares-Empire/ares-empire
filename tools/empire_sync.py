#!/usr/bin/env python3
"""empire_sync — auto-update the Ares Empire hub from the repos themselves.

Runs on a schedule (GitHub Action, once/24h). For every GitHub repo named
`ares…` it reads the repo's docs (README, CLAUDE.md, docs/*) and recent commit
subjects, asks a free LLM (Groq) to fill the hub's boxes — blurb, about,
features, wip, ideas, and a proposed status — then merges the result into
`data/state.json` (the live source the hub serves at /api/empire). aresync pulls
ares-empire on the server and redeploys, so a commit here lands on the hub within
~5 minutes. No per-commit markers, no manual editing.

What it preserves (never clobbered by the LLM):
  - `logo`            brand art (the LLM can't draw the marble busts)
  - `url` / `domain`  if already set manually
  - `detail.changelog` (append-only history)
  - any project with `"lock": true` is skipped entirely (hand-tuned — leave alone)

Status: the LLM proposes one from the docs; if the project's domain actually
resolves (HTTP 200) we make sure it reads at least CONQUERED, so the model can't
declare something live that isn't (or mark a live site as still mustering).

New repos appear automatically (added to `projects`, logged to `chronicle`, given
the empire crest as a placeholder logo until you add bespoke art).

Caveat: discovery is GitHub-only — local-only repos (no remote) are invisible
here until pushed. Excludes the hub repo itself (`ares-empire`).

Env (LLM vars mirror ares-empire/.env so the same key/config is reused):
  EMPIRE_GH_TOKEN          GitHub PAT (repo read) — list + read the ares repos.
                           Falls back to GITHUB_TOKEN.
  EMPIRE_LLM_KEY           API key for the LLM (falls back to GROQ_API_KEY).
  EMPIRE_LLM_PROVIDER      groq | nvidia | gemini | openai (default: groq).
  EMPIRE_LLM_MODEL         primary model id.
  EMPIRE_LLM_FALLBACK_MODEL  tried if the primary errors (optional).
  GH_OWNER                 repo owner (default: carlsenares).

All providers are called through the OpenAI-compatible chat-completions API
(just a different base URL), so switching provider is a one-env-var change.

CLI:
  --dry-run   discover + print what would change; no LLM call, no write.
  --only SLUG limit to one repo (for testing).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from datetime import date, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = Path(os.environ.get("EMPIRE_STATE", REPO_ROOT / "data" / "state.json"))
OWNER = os.environ.get("GH_OWNER", "carlsenares")
GH_TOKEN = os.environ.get("EMPIRE_GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
LLM_KEY = os.environ.get("EMPIRE_LLM_KEY") or os.environ.get("GROQ_API_KEY", "")
LLM_PROVIDER = os.environ.get("EMPIRE_LLM_PROVIDER", "groq").lower()
LLM_MODEL = os.environ.get("EMPIRE_LLM_MODEL", "llama-3.3-70b-versatile")
LLM_FALLBACK_MODEL = os.environ.get("EMPIRE_LLM_FALLBACK_MODEL", "")

# Every provider here speaks the OpenAI chat-completions wire format; only the
# base URL differs. Add a row to support a new one.
PROVIDER_BASE = {
    "groq": "https://api.groq.com/openai/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "openai": "https://api.openai.com/v1",
}

API = "https://api.github.com"
# Repos that match ^ares but are NOT provinces.
EXCLUDE = {"ares-empire"}
# Status tiers the hub understands (must mirror state.json STATUS).
LIVE_TIERS = {"CONQUERED", "FORTIFYING"}
VALID_STATUS = {"SCOUTED", "MUSTERING", "BESIEGING", "CONQUERED", "FORTIFYING"}
PLACEHOLDER_LOGO = "brand/ares-bust.png"  # empire crest until bespoke art exists
DOC_CHAR_CAP = 10_000  # per-repo prompt budget


# --- GitHub ---------------------------------------------------------------

def _gh(path: str, params: dict | None = None) -> object:
    r = requests.get(
        f"{API}{path}",
        headers={
            "Authorization": f"Bearer {GH_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def list_ares_repos() -> list[str]:
    """All repos the token owner OWNS (public + private) whose name starts with
    'ares' (case-insensitive), excluding the hub itself. Uses /user/repos so
    private repos are included; filters to OWNER to be safe. Paginates."""
    names: list[str] = []
    page = 1
    while True:
        batch = _gh("/user/repos", {"per_page": 100, "page": page, "affiliation": "owner"})
        if not batch:
            break
        for repo in batch:
            name = repo["name"]
            if repo.get("owner", {}).get("login", "").lower() != OWNER.lower():
                continue
            if re.match(r"^ares", name, re.IGNORECASE) and name.lower() not in EXCLUDE:
                names.append(name)
        if len(batch) < 100:
            break
        page += 1
    return sorted(names, key=str.lower)


def _content(repo: str, path: str) -> str | None:
    """Fetch a text file's decoded content, or None if absent."""
    try:
        data = _gh(f"/repos/{OWNER}/{repo}/contents/{path}")
    except requests.HTTPError:
        return None
    if isinstance(data, dict) and data.get("encoding") == "base64":
        return base64.b64decode(data["content"]).decode("utf-8", "replace")
    return None


def repo_docs(repo: str) -> str:
    """README + CLAUDE.md + docs/*.md + recent commit subjects, capped."""
    parts: list[str] = []
    for path in ("README.md", "CLAUDE.md"):
        text = _content(repo, path)
        if text:
            parts.append(f"### {path}\n{text}")
    # docs/ markdown
    try:
        listing = _gh(f"/repos/{OWNER}/{repo}/contents/docs")
        if isinstance(listing, list):
            for item in listing:
                if item.get("type") == "file" and item["name"].lower().endswith(".md"):
                    text = _content(repo, f"docs/{item['name']}")
                    if text:
                        parts.append(f"### docs/{item['name']}\n{text}")
    except requests.HTTPError:
        pass
    # recent commit subjects (signal of activity / what's WIP)
    try:
        commits = _gh(f"/repos/{OWNER}/{repo}/commits", {"per_page": 10})
        subjects = [c["commit"]["message"].splitlines()[0] for c in commits if c.get("commit")]
        if subjects:
            parts.append("### recent commits\n" + "\n".join(f"- {s}" for s in subjects))
    except (requests.HTTPError, KeyError):
        pass
    blob = "\n\n".join(parts)
    return blob[:DOC_CHAR_CAP]


def domain_live(domain: str) -> bool:
    if not domain:
        return False
    url = domain if domain.startswith("http") else f"https://{domain}"
    try:
        return requests.get(url, timeout=10, allow_redirects=True).status_code == 200
    except requests.RequestException:
        return False


# --- LLM (Groq) -----------------------------------------------------------

_SYSTEM = (
    "Du befüllst die Projekt-Kacheln einer Portfolio-Website ('Ares Empire'). "
    "Aus den Repo-Dokumenten erzeugst du EINEN Eintrag. Stil der 'blurb': kurz, "
    "evokativ, ein Gedankenstrich (—), martialisch-elegant aber nicht pathetisch, "
    "max ~90 Zeichen (z. B. 'Personal finance command — VR Bank + PayPal, imported "
    "and understood.'). 'about': 1–2 schlichte Sätze. features/wip/ideas: kurze "
    "konkrete Stichpunkte (features im Präsens, was es kann; wip: aktuell in Arbeit; "
    "ideas: Zukunft). 'domain': nur falls in den Docs eine Live-URL genannt ist, "
    "sonst leer. 'status' aus: SCOUTED (nur Idee), MUSTERING (Gerüst/früh), "
    "BESIEGING (aktive Entwicklung), CONQUERED (live & in Betrieb), FORTIFYING "
    "(live, Wartung). Wähle anhand der Signale in den Docs. Antworte AUSSCHLIESSLICH "
    'mit JSON: {"name","blurb","about","status","domain",'
    '"features":[],"wip":[],"ideas":[]}.'
)


def llm_entry(repo: str, docs: str) -> dict:
    from openai import OpenAI

    base = PROVIDER_BASE.get(LLM_PROVIDER)
    if not base:
        raise RuntimeError(f"unknown EMPIRE_LLM_PROVIDER={LLM_PROVIDER!r}")
    client = OpenAI(api_key=LLM_KEY, base_url=base)
    user = f"Repo-Name: {repo}\n\nDokumente:\n{docs or '(keine Dokumente gefunden)'}"
    models = [m for m in (LLM_MODEL, LLM_FALLBACK_MODEL) if m]
    last_exc: Exception | None = None
    for model in models:
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": user},
                ],
            )
            return json.loads(resp.choices[0].message.content or "{}")
        except Exception as exc:  # try the fallback model before giving up
            last_exc = exc
    raise last_exc or RuntimeError("no model configured")


# --- merge ----------------------------------------------------------------

def _as_list(v) -> list[str]:
    return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []


def merge_project(existing: dict | None, repo: str, gen: dict) -> tuple[dict, str | None]:
    """Produce the merged project dict + an optional chronicle note (status change
    or new province). Preserves brand/url/changelog from `existing`."""
    slug = repo.lower()
    existing = existing or {}
    detail = dict(existing.get("detail") or {})

    status = str(gen.get("status", "")).upper()
    if status not in VALID_STATUS:
        status = existing.get("status") or "MUSTERING"
    domain = (gen.get("domain") or existing.get("domain") or "").strip()
    if domain_live(domain) and status not in LIVE_TIERS:
        status = "CONQUERED"

    detail.update(
        about=str(gen.get("about", detail.get("about", ""))).strip(),
        features=_as_list(gen.get("features")) or detail.get("features", []),
        wip=_as_list(gen.get("wip")),
        ideas=_as_list(gen.get("ideas")) or detail.get("ideas", []),
    )
    detail.setdefault("setup", existing.get("detail", {}).get("setup", ""))
    detail.setdefault("changelog", existing.get("detail", {}).get("changelog", []))  # append-only

    merged = {
        "slug": slug,
        "name": str(gen.get("name") or existing.get("name") or repo).strip(),
        "url": existing.get("url", f"https://{domain}" if domain else ""),
        "logo": existing.get("logo") or PLACEHOLDER_LOGO,
        "status": status,
        "domain": domain,
        "blurb": str(gen.get("blurb", existing.get("blurb", ""))).strip(),
        "detail": detail,
    }
    if existing.get("lock"):
        merged["lock"] = True

    note = None
    if not existing:
        note = f"Mustered {merged['name']} into the circle"
    elif existing.get("status") != status:
        note = f"{merged['name']}: {existing.get('status')} → {status}"
    return merged, note


def run(*, dry_run: bool, only: str | None) -> int:
    state = json.loads(STATE_PATH.read_text("utf-8"))
    by_slug = {p["slug"]: p for p in state.get("projects", [])}
    repos = list_ares_repos()
    if only:
        repos = [r for r in repos if r.lower() == only.lower()]
    print(f"discovered {len(repos)} ares repo(s): {', '.join(repos) or '(none)'}", file=sys.stderr)

    new_projects: list[dict] = []
    notes: list[dict] = []
    today = date.today().isoformat()

    for repo in repos:
        slug = repo.lower()
        existing = by_slug.get(slug)
        if existing and existing.get("lock"):
            print(f"  {slug}: locked — skip", file=sys.stderr)
            continue
        if dry_run:
            print(f"  {slug}: would {'refresh' if existing else 'ADD'}", file=sys.stderr)
            continue
        try:
            gen = llm_entry(repo, repo_docs(repo))
        except Exception as exc:  # one bad repo never sinks the run
            print(f"  {slug}: LLM/read failed ({exc}); keeping existing", file=sys.stderr)
            continue
        merged, note = merge_project(existing, repo, gen)
        if existing:
            by_slug[slug].clear()
            by_slug[slug].update(merged)
        else:
            by_slug[slug] = merged
            new_projects.append(merged)
        if note:
            notes.append({"at": today, "project": slug, "text": note})
        print(f"  {slug}: {merged['status']} — {merged['blurb'][:60]}", file=sys.stderr)

    if dry_run:
        return 0

    # Rebuild projects preserving original order, then append truly-new ones.
    ordered = [by_slug[p["slug"]] for p in state["projects"]]
    ordered += [p for p in new_projects if p not in ordered]
    state["projects"] = ordered
    state.setdefault("chronicle", [])
    state["chronicle"] = notes + state["chronicle"]  # newest first

    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(f"wrote {STATE_PATH} ({len(ordered)} provinces, +{len(notes)} chronicle)", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="empire_sync")
    ap.add_argument("--dry-run", action="store_true", help="discover + report; no LLM, no write")
    ap.add_argument("--only", help="limit to one repo (testing)")
    args = ap.parse_args(argv)
    if not GH_TOKEN:
        print("error: set EMPIRE_GH_TOKEN (or GITHUB_TOKEN)", file=sys.stderr)
        return 2
    if not args.dry_run and not LLM_KEY:
        print("error: set EMPIRE_LLM_KEY (or use --dry-run)", file=sys.stderr)
        return 2
    return run(dry_run=args.dry_run, only=args.only)


if __name__ == "__main__":
    raise SystemExit(main())
