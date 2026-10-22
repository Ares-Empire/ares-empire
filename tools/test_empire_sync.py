"""Tests for empire_sync. No network: GitHub, the LLM and the domain check are replaced.

Run: .venv-empire-sync/bin/python -m unittest tools/test_empire_sync.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import empire_sync as es  # noqa: E402

TODAY = date(2026, 10, 22)

README = """# AresOS

[![build](https://img.shields.io/badge/x.svg)](https://ci)

A Minecraft-themed operating system. Linux that boots into your Nether, with **mods** as apps.

## Features
- Boots straight into a [block world](https://example.com)
- Inventory is the file manager

## Setup
```
make iso
```
"""


def repo(name, pushed="2026-10-22T10:00:00Z", description="", homepage=None):
    return {"name": name, "pushed_at": pushed, "description": description, "homepage": homepage}


def project(slug, **kw):
    base = {"slug": slug, "name": slug.title(), "url": "", "logo": f"brand/{slug}.png",
            "status": "BESIEGING", "domain": "", "blurb": f"Hand-written {slug} blurb.",
            "detail": {"about": f"About {slug}.", "features": ["one"], "wip": [], "ideas": [],
                       "setup": "", "changelog": [{"at": "2026-07-01", "text": "old"}]}}
    base.update(kw)
    return base


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.state_path = self.tmp / "state.json"
        self.meta_path = self.tmp / "sync-meta.json"
        self.patches = [
            mock.patch.object(es, "STATE_PATH", self.state_path),
            mock.patch.object(es, "META_PATH", self.meta_path),
            mock.patch.object(es, "domain_live", lambda d: False),
            mock.patch.object(es, "_content", lambda r, p: README if p == "README.md" else None),
            mock.patch.object(es, "repo_docs", lambda r, readme: readme or ""),
            mock.patch.object(es, "repo_changelog", lambda r: [{"at": "2026-10-22", "text": f"{r} commit"}]),
            mock.patch.object(es, "LLM_KEY", "key"),
            mock.patch.object(es, "LLM_MODELS", ["m1"]),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def write_state(self, projects):
        self.state_path.write_text(json.dumps({"projects": projects, "chronicle": []}))

    def run_sync(self, repos, llm=None, **kw):
        llm = llm or mock.Mock(side_effect=RuntimeError("model gone"))
        with mock.patch.object(es, "list_ares_repos", lambda: repos), \
             mock.patch.object(es, "llm_entry", llm):
            code = es.run(dry_run=False, only=None, use_llm=True, force=False, today=TODAY, **kw)
        self.assertEqual(code, 0)
        state = json.loads(self.state_path.read_text())
        return {p["slug"]: p for p in state["projects"]}, state, llm


class NewRepos(Base):
    def test_new_repo_is_added_even_when_every_model_fails(self):
        self.write_state([project("aresium", lock=True)])
        projects, state, _ = self.run_sync([repo("AresOS", description="A Minecraft-themed OS: Linux that boots into your Nether")])
        os_ = projects["aresos"]
        self.assertEqual(os_["name"], "AresOS")
        self.assertTrue(os_["blurb"].startswith("A Minecraft-themed OS"))
        self.assertIn("Minecraft-themed operating system", os_["detail"]["about"])
        self.assertEqual(os_["detail"]["features"], ["Boots straight into a block world", "Inventory is the file manager"])
        self.assertEqual(os_["status"], "BESIEGING")  # pushed today
        self.assertEqual(os_["logo"], es.PLACEHOLDER_LOGO)
        self.assertEqual(state["chronicle"][0]["text"], "Mustered AresOS into the circle")
        meta = json.loads(self.meta_path.read_text())
        self.assertTrue(meta["repos"]["aresos"]["needs_llm"])
        self.assertIn("model gone", meta["last_errors"][0])

    def test_new_repo_uses_llm_text_when_it_works(self):
        self.write_state([])
        gen = {"name": "AresOS", "blurb": "Nether OS — boots into blocks.", "about": "x", "status": "MUSTERING",
               "features": ["f"], "wip": ["w"], "ideas": ["i"], "domain": ""}
        projects, _, _ = self.run_sync([repo("AresOS")], llm=mock.Mock(return_value=gen))
        self.assertEqual(projects["aresos"]["blurb"], "Nether OS — boots into blocks.")
        self.assertEqual(projects["aresos"]["status"], "MUSTERING")
        self.assertFalse(json.loads(self.meta_path.read_text())["repos"]["aresos"]["needs_llm"])

    def test_old_repo_without_description_falls_back_to_readme_and_is_mustering(self):
        self.write_state([])
        projects, _, _ = self.run_sync([repo("AresOS", pushed="2026-01-01T00:00:00Z")])
        self.assertEqual(projects["aresos"]["blurb"], "A Minecraft-themed operating system.")
        self.assertEqual(projects["aresos"]["status"], "MUSTERING")


class ExistingRepos(Base):
    def test_unchanged_repo_is_left_alone(self):
        self.write_state([project("aresync")])
        self.meta_path.write_text(json.dumps({"repos": {"aresync": {"pushed_at": "2026-10-22T10:00:00Z", "needs_llm": False}}}))
        projects, _, llm = self.run_sync([repo("aresync")])
        llm.assert_not_called()
        self.assertEqual(projects["aresync"]["detail"]["changelog"], [{"at": "2026-07-01", "text": "old"}])

    def test_changed_repo_keeps_its_text_when_llm_fails_but_gets_new_commits(self):
        self.write_state([project("aresync")])
        self.meta_path.write_text(json.dumps({"repos": {"aresync": {"pushed_at": "2026-06-01T00:00:00Z"}}}))
        projects, state, _ = self.run_sync([repo("aresync")])
        p = projects["aresync"]
        self.assertEqual(p["blurb"], "Hand-written aresync blurb.")
        self.assertEqual(p["detail"]["about"], "About aresync.")
        self.assertEqual(p["logo"], "brand/aresync.png")
        self.assertEqual(p["status"], "BESIEGING")
        self.assertEqual(p["detail"]["changelog"][0], {"at": "2026-10-22", "text": "aresync commit"})
        self.assertEqual(state["chronicle"], [])

    def test_llm_is_tried_at_most_once_a_day(self):
        self.write_state([project("aresync")])
        self.meta_path.write_text(json.dumps({"repos": {"aresync": {
            "pushed_at": "2026-10-22T10:00:00Z", "needs_llm": True, "llm_attempt": TODAY.isoformat()}}}))
        _, _, llm = self.run_sync([repo("aresync")])
        llm.assert_not_called()

    def test_failed_polish_is_retried_the_next_day_without_a_new_push(self):
        self.write_state([project("aresync")])
        self.meta_path.write_text(json.dumps({"repos": {"aresync": {
            "pushed_at": "2026-10-22T10:00:00Z", "needs_llm": True, "llm_attempt": "2026-10-21"}}}))
        _, _, llm = self.run_sync([repo("aresync")])
        llm.assert_called_once()

    def test_locked_and_local_only_projects_are_untouched(self):
        locked = project("aresium", lock=True)
        local = project("arescrypt")  # no GitHub repo
        self.write_state([locked, local])
        projects, _, _ = self.run_sync([repo("aresium")])
        self.assertEqual(projects["aresium"], locked)
        self.assertEqual(projects["arescrypt"], local)

    def test_order_is_kept_and_new_repos_come_last(self):
        self.write_state([project("b"), project("a")])
        state = self.run_sync([repo("AresOS")])[1]
        self.assertEqual([p["slug"] for p in state["projects"]], ["b", "a", "aresos"])


class Text(unittest.TestCase):
    def test_readme_intro_skips_headings_badges_and_code(self):
        self.assertEqual(es.readme_intro(README),
                         "A Minecraft-themed operating system. Linux that boots into your Nether, with mods as apps.")

    def test_first_sentence_is_capped_at_a_word(self):
        s = es.first_sentence("word " * 40)
        self.assertLessEqual(len(s), es.BLURB_CAP)
        self.assertTrue(s.endswith("…"))

    def test_homepage_domain(self):
        self.assertEqual(es.homepage_domain("https://aresium.de/"), "aresium.de")
        self.assertEqual(es.homepage_domain(None), "")


if __name__ == "__main__":
    unittest.main()
