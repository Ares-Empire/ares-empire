#!/usr/bin/env python3
"""empire_sync — keep the Ares Empire hub in step with the `ares…` repos on GitHub.

Runs hourly (systemd timer empire-sync.timer). For every GitHub repo whose name starts with
`ares` (case-insensitive, excluding the hub itself):

1. **New repo → always added.** Its tile is built from GitHub alone: name, the repo
   description (or the README's first paragraph), website field, recent commits, and a status
   from activity. No LLM needed, so a new repo appears within the hour even when every model
   is down (that was the old failure: LLM down → new repos silently skipped).
2. **Changed repo (new push) → refreshed:** changelog and status always; text only when the
   LLM polish succeeds (good existing text is never replaced by the plain fallback).
3. **LLM polish (optional):** tries each configured model with a short timeout, at most once
   per repo per day. Failure is logged and retried the next day; it never blocks 1. or 2.

What it preserves (never overwritten):
  - `logo`, and `url` / `domain` if already set by hand
  - `detail.changelog` (append-only history)
  - any project with `"lock": true` (hand-tuned, skipped entirely)
  - hub entries with no GitHub repo (local-only projects): never touched or removed

Bookkeeping lives in `data/sync-meta.json` (last push seen and last LLM attempt per repo, last
run and its errors), so `data/state.json`, which the hub serves, stays clean.

Env:
  EMPIRE_GH_TOKEN            GitHub PAT (repo read). Falls back to GITHUB_TOKEN.
  EMPIRE_LLM_PROVIDER        groq | nvidia | gemini | openai (default: groq).
  EMPIRE_LLM_KEY             API key (falls back to GROQ_API_KEY). Empty = no polish.
  EMPIRE_LLM_MODELS          comma-separated models, tried in order. Else EMPIRE_LLM_MODEL
                             and EMPIRE_LLM_FALLBACK_MODEL.
  EMPIRE_LLM_TIMEOUT         seconds per model call (default 45).
  GH_OWNER                   repo owner (default: carlsenares).

CLI:
  --dry-run       report what would change; no LLM call, no write.
  --only SLUG     limit to one repo.
  --no-llm        skip the LLM polish this run.
  --force         treat every repo as changed (re-read all).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = Path(os.environ.get("EMPIRE_STATE", REPO_ROOT / "data" / "state.json"))
META_PATH = Path(os.environ.get("EMPIRE_SYNC_META", REPO_ROOT / "data" / "sync-meta.json"))
OWNER = os.environ.get("GH_OWNER", "carlsenares")
GH_TOKEN = os.environ.get("EMPIRE_GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
LLM_KEY = os.environ.get("EMPIRE_LLM_KEY") or os.environ.get("GROQ_API_KEY", "")
LLM_PROVIDER = os.environ.get("EMPIRE_LLM_PROVIDER", "groq").lower()
LLM_MODELS = [m.strip() for m in os.environ.get("EMPIRE_LLM_MODELS", "").split(",") if m.strip()] or [
    m for m in (os.environ.get("EMPIRE_LLM_MODEL", "llama-3.3-70b-versatile"),
                os.environ.get("EMPIRE_LLM_FALLBACK_MODEL", "")) if m
]
LLM_TIMEOUT = float(os.environ.get("EMPIRE_LLM_TIMEOUT", "45"))
# Telegram (the aresync bot, one feed with the laptops). Empty = no ping.
TG_TOKEN = os.environ.get("ARESYNC_TG_TOKEN", "")
TG_CHAT = os.environ.get("ARESYNC_TG_CHAT", "")

PROVIDER_BASE = {
    "groq": "https://api.groq.com/openai/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "openai": "https://api.openai.com/v1",
}

API = "https://api.github.com"
EXCLUDE = {"ares-empire"}  # matches ^ares but is the hub itself
LIVE_TIERS = {"CONQUERED", "FORTIFYING"}
VALID_STATUS = {"SCOUTED", "MUSTERING", "BESIEGING", "CONQUERED", "FORTIFYING"}
PLACEHOLDER_LOGO = "brand/ares-bust.png"  # empire crest until bespoke art exists
DOC_CHAR_CAP = 10_000
CHANGELOG_CAP = 20
BLURB_CAP = 90
ACTIVE_DAYS = 30  # pushed within this many days → BESIEGING


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


def list_ares_repos() -> list[dict]:
    """Repos the token owner owns (public + private) named ares…, excluding the hub, archived
    repos and forks. Returns GitHub's repo objects (name, description, homepage, pushed_at…)."""
    repos: list[dict] = []
    page = 1
    while True:
        batch = _gh("/user/repos", {"per_page": 100, "page": page, "affiliation": "owner"})
        if not batch:
            break
        for repo in batch:
            name = repo["name"]
            if repo.get("owner", {}).get("login", "").lower() != OWNER.lower():
                continue
            if repo.get("archived") or repo.get("fork"):
                continue
            if re.match(r"^ares", name, re.IGNORECASE) and name.lower() not in EXCLUDE:
                repos.append(repo)
        if len(batch) < 100:
            break
        page += 1
    return sorted(repos, key=lambda r: r["name"].lower())


def _content(repo: str, path: str) -> str | None:
    try:
        data = _gh(f"/repos/{OWNER}/{repo}/contents/{path}")
    except requests.HTTPError:
        return None
    if isinstance(data, dict) and data.get("encoding") == "base64":
        return base64.b64decode(data["content"]).decode("utf-8", "replace")
    return None


def repo_docs(repo: str, readme: str | None) -> str:
    """README + CLAUDE.md + docs/*.md + recent commit subjects, capped (for the LLM)."""
    parts: list[str] = []
    if readme:
        parts.append(f"### README.md\n{readme}")
    claude = _content(repo, "CLAUDE.md")
    if claude:
        parts.append(f"### CLAUDE.md\n{claude}")
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
    return "\n\n".join(parts)[:DOC_CHAR_CAP]


def repo_changelog(repo: str) -> list[dict]:
    """Recent real commits as {"at": YYYY-MM-DD, "text": subject}, newest first. Skips aresync
    auto-commits and merges."""
    try:
        commits = _gh(f"/repos/{OWNER}/{repo}/commits", {"per_page": 30})
    except requests.RequestException:
        return []
    out: list[dict] = []
    if not isinstance(commits, list):
        return out
    for c in commits:
        commit = c.get("commit") or {}
        subject = (commit.get("message") or "").splitlines()[0].strip()
        if not subject or subject.startswith(("Aresync auto-commit", "Merge ")):
            continue
        when = (commit.get("author") or commit.get("committer") or {}).get("date", "")[:10]
        out.append({"at": when, "text": subject})
    return out


def tg_notify(lines: list[str]) -> None:
    if not (TG_TOKEN and TG_CHAT and lines):
        return
    import socket

    host = socket.gethostname().split(".")[0]
    text = f"🏛 <b>Empire hub updated</b> · {host}\n" + "\n".join(lines)
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=15,
        )
    except requests.RequestException as exc:
        print(f"telegram notify failed: {exc}", file=sys.stderr)


def domain_live(domain: str) -> bool:
    if not domain:
        return False
    url = domain if domain.startswith("http") else f"https://{domain}"
    try:
        return requests.get(url, timeout=10, allow_redirects=True).status_code == 200
    except requests.RequestException:
        return False


# --- basic entry from GitHub alone (no LLM) ------------------------------

_MD_NOISE = re.compile(r"!\[[^\]]*\]\([^)]*\)|<[^>]+>|\[!\[.*?\]\(.*?\)\]\(.*?\)")


def readme_intro(readme: str | None) -> str:
    """First prose paragraph of a README: skips headings, badges, code, tables, lists."""
    if not readme:
        return ""
    paragraph: list[str] = []
    in_code = False
    for raw in readme.splitlines():
        line = raw.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if not line:
            if paragraph:
                break
            continue
        if line.startswith(("#", "|", "-", "*", ">", "=", "---")) or re.match(r"^\d+\.", line):
            if paragraph:
                break
            continue
        line = _MD_NOISE.sub("", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)  # links → text
        line = re.sub(r"[*_`]{1,3}", "", line).strip()
        if line:
            paragraph.append(line)
    return " ".join(paragraph).strip()


def first_sentence(text: str, cap: int = BLURB_CAP) -> str:
    text = text.strip()
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    sentence = m.group(1) if m else text
    if len(sentence) <= cap:
        return sentence
    cut = sentence[: cap - 1].rsplit(" ", 1)[0]
    return cut.rstrip(",;:—- ") + "…"


def readme_features(readme: str | None, limit: int = 6) -> list[str]:
    """Bullets under a 'Features' heading, if the README has one."""
    if not readme:
        return []
    out: list[str] = []
    in_section = False
    for raw in readme.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            in_section = bool(re.search(r"feature|what it does|funktion", line, re.IGNORECASE))
            continue
        if in_section and re.match(r"^[-*]\s+", line):
            item = re.sub(r"^[-*]\s+", "", line)
            item = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", item)
            item = re.sub(r"[*_`]{1,3}", "", item).strip()
            if item:
                out.append(item)
            if len(out) >= limit:
                break
    return out


def activity_status(pushed_at: str, today: date) -> str:
    try:
        pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        return "MUSTERING"
    return "BESIEGING" if (today - pushed) <= timedelta(days=ACTIVE_DAYS) else "MUSTERING"


def homepage_domain(homepage: str | None) -> str:
    if not homepage:
        return ""
    return re.sub(r"^https?://", "", homepage.strip()).rstrip("/")


def basic_entry(repo: dict, readme: str | None, today: date) -> dict:
    """A complete tile from GitHub data alone, in the same shape the LLM returns."""
    intro = readme_intro(readme)
    description = (repo.get("description") or "").strip()
    return {
        "name": repo["name"],
        "blurb": first_sentence(description or intro or f"{repo['name']} — new province."),
        "about": intro or description,
        "status": activity_status(repo.get("pushed_at", ""), today),
        "domain": homepage_domain(repo.get("homepage")),
        "features": readme_features(readme),
        "wip": [],
        "ideas": [],
    }


# --- LLM polish (optional) -------------------------------------------------

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
    """Ask the configured models in order; the first valid JSON answer wins."""
    from openai import OpenAI

    base = PROVIDER_BASE.get(LLM_PROVIDER)
    if not base:
        raise RuntimeError(f"unknown EMPIRE_LLM_PROVIDER={LLM_PROVIDER!r}")
    client = OpenAI(api_key=LLM_KEY, base_url=base, timeout=LLM_TIMEOUT, max_retries=0)
    user = f"Repo-Name: {repo}\n\nDokumente:\n{docs or '(keine Dokumente gefunden)'}"
    errors: list[str] = []
    for model in LLM_MODELS:
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": _SYSTEM},
                          {"role": "user", "content": user}],
            )
            gen = json.loads(resp.choices[0].message.content or "{}")
            if isinstance(gen, dict) and gen.get("blurb"):
                return gen
            errors.append(f"{model}: empty answer")
        except Exception as exc:  # next model
            errors.append(f"{model}: {str(exc)[:120]}")
    raise RuntimeError("; ".join(errors) or "no model configured")


# --- merge ----------------------------------------------------------------

def _as_list(v) -> list[str]:
    return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []


def merge_project(existing: dict | None, repo: str, gen: dict | None,
                  changelog_new: list[dict], fallback_status: str,
                  fallback: dict | None = None) -> tuple[dict, str | None]:
    """Merged project + optional chronicle note.

    `gen` is the LLM answer (or None if it failed or was skipped). Text fields come from `gen`;
    without it, an existing project keeps its text and a new one uses `fallback` (the basic
    entry). Status: `gen`'s if valid, else the existing one, else `fallback_status`; a live
    domain lifts it to CONQUERED. Logo, url, domain set by hand, and the changelog history are
    always kept."""
    slug = repo.lower()
    existing = existing or {}
    text = gen or (fallback if not existing else None) or {}
    detail = dict(existing.get("detail") or {})

    status = str((gen or {}).get("status", "")).upper()
    if status not in VALID_STATUS:
        status = existing.get("status") or fallback_status
    domain = (existing.get("domain") or text.get("domain") or (fallback or {}).get("domain") or "").strip()
    if domain_live(domain) and status not in LIVE_TIERS:
        status = "CONQUERED"

    if text:
        detail.update(
            about=str(text.get("about", detail.get("about", ""))).strip(),
            features=_as_list(text.get("features")) or detail.get("features", []),
            wip=_as_list(text.get("wip")),
            ideas=_as_list(text.get("ideas")) or detail.get("ideas", []),
        )
    detail.setdefault("about", "")
    detail.setdefault("features", [])
    detail.setdefault("wip", [])
    detail.setdefault("ideas", [])
    detail.setdefault("setup", "")
    existing_log = (existing.get("detail") or {}).get("changelog") or []
    seen = {(e.get("at"), e.get("text")) for e in existing_log}
    fresh = [e for e in changelog_new if (e.get("at"), e.get("text")) not in seen]
    detail["changelog"] = (fresh + existing_log)[:CHANGELOG_CAP]

    merged = {
        "slug": slug,
        "name": str(text.get("name") or existing.get("name") or repo).strip(),
        "url": existing.get("url") or (f"https://{domain}" if domain else ""),
        "logo": existing.get("logo") or PLACEHOLDER_LOGO,
        "status": status,
        "domain": domain,
        "blurb": str(text.get("blurb") or existing.get("blurb") or "").strip(),
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


# --- run --------------------------------------------------------------------

def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", "utf-8")
    tmp.replace(path)  # atomic: the hub never reads a half-written file


def run(*, dry_run: bool, only: str | None, use_llm: bool, force: bool,
        today: date | None = None) -> int:
    today = today or date.today()
    state = _load_json(STATE_PATH, None)
    if state is None:
        print(f"error: cannot read {STATE_PATH}", file=sys.stderr)
        return 2
    meta = _load_json(META_PATH, {"repos": {}})
    meta.setdefault("repos", {})
    by_slug = {p["slug"]: p for p in state.get("projects", [])}
    repos = list_ares_repos()
    if only:
        repos = [r for r in repos if r["name"].lower() == only.lower()]
    print(f"discovered {len(repos)} ares repo(s): {', '.join(r['name'] for r in repos) or '(none)'}",
          file=sys.stderr)

    new_projects: list[dict] = []
    notes: list[dict] = []
    errors: list[str] = []
    llm_ready = use_llm and bool(LLM_KEY) and bool(LLM_MODELS)

    for repo in repos:
        name = repo["name"]
        slug = name.lower()
        existing = by_slug.get(slug)
        seen = meta["repos"].get(slug, {})
        if existing and existing.get("lock"):
            print(f"  {slug}: locked — skip", file=sys.stderr)
            continue
        changed = force or not existing or seen.get("pushed_at") != repo.get("pushed_at")
        retry_llm = existing and seen.get("needs_llm") and seen.get("llm_attempt") != today.isoformat()
        if not (changed or retry_llm):
            continue
        if dry_run:
            print(f"  {slug}: would {'refresh' if existing else 'ADD'}", file=sys.stderr)
            continue

        readme = _content(name, "README.md")
        fallback = basic_entry(repo, readme, today)
        gen = None
        if llm_ready and seen.get("llm_attempt") != today.isoformat():
            seen["llm_attempt"] = today.isoformat()
            try:
                gen = llm_entry(name, repo_docs(name, readme) + _commit_block(name))
            except Exception as exc:
                errors.append(f"{slug}: LLM failed ({str(exc)[:200]})")
        merged, note = merge_project(existing, name, gen, repo_changelog(name),
                                     fallback["status"], fallback)
        seen["pushed_at"] = repo.get("pushed_at")
        seen["needs_llm"] = gen is None
        meta["repos"][slug] = seen
        if existing:
            existing.clear()
            existing.update(merged)
        else:
            by_slug[slug] = merged
            new_projects.append(merged)
        if note:
            notes.append({"at": today.isoformat(), "project": slug, "text": note})
        source = "LLM" if gen else ("from GitHub" if not existing else "text kept")
        print(f"  {slug}: {merged['status']} ({source}) — {merged['blurb'][:60]}", file=sys.stderr)

    if dry_run:
        return 0

    state["projects"] = [by_slug[p["slug"]] for p in state.get("projects", [])] + new_projects
    state["chronicle"] = notes + state.get("chronicle", [])  # newest first
    _write_json(STATE_PATH, state)  # changelogs may have moved even without notes
    meta["last_run"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    meta["last_errors"] = errors
    _write_json(META_PATH, meta)
    for e in errors:
        print(f"  {e}", file=sys.stderr)
    print(f"wrote {STATE_PATH} ({len(state['projects'])} provinces, +{len(new_projects)} new, "
          f"+{len(notes)} chronicle, {len(errors)} LLM error(s))", file=sys.stderr)
    tg_notify([f"• {n['text']}" for n in notes])
    return 0


def _commit_block(repo: str) -> str:
    subjects = [e["text"] for e in repo_changelog(repo)[:10]]
    return ("\n\n### recent commits\n" + "\n".join(f"- {s}" for s in subjects)) if subjects else ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="empire_sync")
    ap.add_argument("--dry-run", action="store_true", help="report only; no LLM, no write")
    ap.add_argument("--only", help="limit to one repo")
    ap.add_argument("--no-llm", action="store_true", help="skip the LLM polish this run")
    ap.add_argument("--force", action="store_true", help="treat every repo as changed")
    args = ap.parse_args(argv)
    if not GH_TOKEN:
        print("error: set EMPIRE_GH_TOKEN (or GITHUB_TOKEN)", file=sys.stderr)
        return 2
    return run(dry_run=args.dry_run, only=args.only, use_llm=not args.no_llm, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
