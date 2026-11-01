"""The fixture generator (tools/empire_samples.py): it runs, every file is the hub server's own answer, and the
contract checks catch what they should. Run from the repo root: python3 -m unittest tools/test_empire_samples.py"""
import copy
import json
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from urllib.parse import urlsplit

from tools import empire_samples as samples
from webauth import contact, server

IP = "127.0.0.1"


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        with redirect_stdout(StringIO()):
            samples.main([cls.folder.name])
        cls.files = {path.name: json.loads(path.read_text(encoding="utf-8"))
                     for path in Path(cls.folder.name).glob("*.json")}

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_writes_every_fixture(self):
        self.assertEqual(set(self.files), {
            "empire.admin.json", "empire.member.json", "empire.new-member.json", "empire.requested.json",
            "access-request.json", "approvals.json", "approval-decision.json",
            *(f"error.{code}.json" for code in server.ERROR_CODES)})

    def test_each_file_is_the_servers_answer(self):
        accounts = samples.ACCOUNTS
        with samples.fake_world():
            for name, token in (("empire.admin.json", "sample-admin-token"),
                                ("empire.member.json", "sample-member-token"),
                                ("empire.new-member.json", "sample-new-member-token"),
                                ("empire.requested.json", "sample-requested-token")):
                with self.subTest(name=name):
                    self.assertEqual(self.files[name], server.empire_data(accounts[token], token, IP, "en"))
            self.assertEqual(self.files["access-request.json"], server.request_access(
                accounts["sample-new-member-token"], "sample-new-member-token", IP, {"service": "arestemis"}, "en"))
            approvals = server.pending_accounts("sample-admin-token", IP)
            self.assertEqual(self.files["approvals.json"], approvals)
            card = approvals[1]
            self.assertFalse(card["approved"])
            self.assertEqual(self.files["approval-decision.json"], server.decide_approval(
                card["id"], "sample-admin-token", IP, {"approve": True, "requested": card["requested"]}))

    def test_each_file_has_the_contracts_shape(self):
        for name, data in self.files.items():
            check = (samples.check_empire if name.startswith("empire.") or name == "access-request.json" else
                     samples.check_approvals if name == "approvals.json" else
                     samples.check_decision if name == "approval-decision.json" else samples.check_error)
            with self.subTest(name=name):
                self.assertEqual(check(data), [])
        for code in server.ERROR_CODES:
            self.assertEqual(self.files[f"error.{code}.json"]["code"], code)

    def test_the_accounts_see_what_the_contract_says(self):
        admin, member, new, asked = (self.files[f"empire.{who}.json"]
                                     for who in ("admin", "member", "new-member", "requested"))
        seed = samples.read_seed()
        self.assertEqual([p["slug"] for p in admin["projects"]], [p["slug"] for p in seed["projects"]])
        self.assertEqual((len(admin["chronicle"]), len(admin["ideas"])), (len(seed["chronicle"]), len(seed["ideas"])))
        self.assertEqual(admin["pending"], len(self.files["approvals.json"]))
        self.assertTrue(all((p["state"], p["access"]) == ("open", "granted") for p in admin["projects"]))
        self.assertEqual(admin["addable"], [])
        # The member's ring is its one app, with the install link; the "+" holds the rest of the catalog.
        self.assertEqual([(p["slug"], p["access"], p["install"]) for p in member["projects"]],
                         [("arestemis", "granted", samples.SAMPLE_INSTALL["arestemis"])])
        self.assertTrue(member["chronicle"] and all(e["project"] == "arestemis" for e in member["chronicle"]))
        self.assertEqual([(p["slug"], p["state"], p["access"]) for p in member["addable"]],
                         [("aresium", "coming-soon", "none")])
        self.assertEqual((new["projects"], new["chronicle"], new["ideas"], new["pending"]), ([], [], [], 0))
        self.assertEqual([(p["slug"], p["state"], p["access"], p["install"]) for p in new["addable"]],
                         [("aresium", "coming-soon", "none", None), ("arestemis", "open", "none", None)])
        self.assertEqual([(p["slug"], p["access"]) for p in asked["addable"]],
                         [("aresium", "none"), ("arestemis", "requested")])
        # The request answer: the new member's hub data, Arestemis now asked for.
        answer = self.files["access-request.json"]
        self.assertEqual(answer["me"], new["me"])
        self.assertEqual(answer["addable"], asked["addable"])
        self.assertEqual(sorted({a["verified"] for a in self.files["approvals.json"]}), [False, True])

    def test_the_websites_previews_are_current(self):
        # The localhost preview (web/app/empire-api.js) loads these; they are the generator's output, not hand-made.
        for name in samples.WEB_PREVIEWS:
            with self.subTest(name=name):
                self.assertEqual((samples.WEB_SAMPLES / name).read_text(encoding="utf-8"), samples.dump(self.files[name]),
                                 "run python3 tools/empire_samples.py --web")
        # The public demo's two files (www.ares-empire.de/demo) are the generator's output too.
        self.assertEqual((samples.WEB_SAMPLES / samples.DEMO_FILE).read_text(encoding="utf-8"),
                         samples.dump(samples.build_demo()), "run python3 tools/empire_samples.py --web")
        self.assertEqual((samples.WEB_SAMPLES / samples.DEMO_WORDS_FILE).read_text(encoding="utf-8"), samples.demo_words(),
                         "run python3 tools/empire_samples.py --web")
        self.assertEqual(sorted(path.name for path in samples.WEB_SAMPLES.glob("*.json")),
                         sorted([*samples.WEB_PREVIEWS, samples.DEMO_FILE]))

    def test_the_demo_holds_only_the_demo(self):
        # A guest with the three apps others can have, the demo's own texts and chronicle, nothing of the real seed.
        demo, seed = samples.build_demo(), samples.read_seed()
        self.assertEqual(demo["me"]["admin"], False)
        self.assertEqual([p["slug"] for p in demo["projects"]], ["aresium", "arestemis", "arestoteles", "aresus", "aresync"])
        self.assertEqual([p["install"] for p in demo["projects"]],
                         ["https://aresium.de/contact?topic=access",
                          "https://www.ares-empire.de/arestemis/contact?topic=access",
                          "https://www.ares-empire.de/contact", None, None])
        self.assertEqual([p["url"] for p in demo["projects"]][1:3],
                         ["https://www.ares-empire.de/arestemis/contact?topic=access", "https://www.ares-empire.de/contact"])
        # the demo's band asks for the Ares Empire app on the Empire's contact page
        api = (samples.WEB_SAMPLES.parent / "empire-api.js").read_text(encoding="utf-8")
        self.assertIn(f'<a href="{samples.EMPIRE_REQUEST}" target="_blank" rel="noopener">Get the app</a>', api)
        # every address is one of the contact pages the hub or aresium.de serves (webauth/contact.py)
        for link in (samples.EMPIRE_REQUEST, samples.ARESTEMIS_REQUEST, samples.DEMO_REQUEST):
            self.assertIn(urlsplit(link).path, contact.PAGES)
        self.assertEqual(demo["chronicle"], samples.DEMO_CHRONICLE)
        self.assertEqual((demo["ideas"], demo["addable"], demo["pending"]), ([], [], 0))
        real = {c["text"] for c in seed["chronicle"]} | {p["blurb"] for p in seed["projects"]}
        shown = {c["text"] for c in demo["chronicle"]} | {p["blurb"] for p in demo["projects"]}
        self.assertEqual(real & shown, set())
        self.assertEqual(demo["projects"][0]["url"], "https://aresium.de/demo")
        words = samples.demo_words()
        self.assertIn('"CONQUERED"', words)
        self.assertNotIn("chronicle", words.split("window.EMPIRE", 1)[1])

    def test_outdir_or_web(self):
        for argv in ([], ["--web", "somewhere"]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit), redirect_stdout(StringIO()), \
                    redirect_stderr(StringIO()):
                samples.main(argv)


class SeedReaderTests(unittest.TestCase):
    def test_reads_the_whole_committed_seed(self):
        source = samples.SEED.read_text(encoding="utf-8")
        seed = samples.read_seed()
        self.assertEqual(len(seed["projects"]), len(re.findall(r"^\s*slug: ", source, re.M)))
        self.assertEqual(len(seed["chronicle"]), len(re.findall(r"^\s*\{ at: ", source, re.M)))
        self.assertEqual(len(seed["ideas"]), len(re.findall(r"^\s*\{ title: ", source, re.M)))
        aresium = seed["projects"][0]
        self.assertEqual((aresium["slug"], aresium["url"], aresium["logo"]),
                         ("aresium", "https://aresium.de", "brand/hermes.webp"))
        self.assertTrue(aresium["detail"]["about"].startswith("The empire's personal-finance command. Aresium"))
        self.assertNotIn('" +', json.dumps(seed))

    def test_reads_plain_javascript(self):
        source = """/* a comment with "quotes" */
        const OTHER = 1;
        const EMPIRE = {
          // a line comment
          projects: [{
            url: "https://example.com/a // not a comment",
            joined: "one " +
              'two \\'quoted\\' ' + "three \\"x\\" \\u00e9",
            "quoted key": [1, 2.5, -3, true, false, null,],
            nested: { list: [], empty: {}, },
          }],
          ideas: [],
          chronicle: [],
          STATUS,
        };
        window.EMPIRE = EMPIRE;"""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "seed.js"
            path.write_text(source, encoding="utf-8")
            seed = samples.read_seed(path)
        self.assertEqual(seed, {"ideas": [], "chronicle": [], "projects": [{
            "url": "https://example.com/a // not a comment",
            "joined": "one two 'quoted' three \"x\" é",
            "quoted key": [1, 2.5, -3, True, False, None],
            "nested": {"list": [], "empty": {}},
        }]})

    def test_names_the_line_it_cannot_read(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "seed.js"
            path.write_text("const EMPIRE = {\n  projects: [\n    `a template`,\n  ],\n};\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "line 3: not plain data"):
                samples.read_seed(path)
            path.write_text("const EMPIRE = {\n  name: \"a\" + 1,\n};\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "line 2: only strings can be joined"):
                samples.read_seed(path)


class ContractCheckTests(unittest.TestCase):
    def setUp(self):
        with samples.fake_world():
            self.admin = server.empire_data(samples.ACCOUNTS["sample-admin-token"], "sample-admin-token", IP)

    def broken(self, change):
        data = copy.deepcopy(self.admin)
        change(data)
        return samples.check_empire(data)

    def test_catches_what_would_break_the_app(self):
        self.assertEqual(samples.check_empire(self.admin), [])
        for label, change in [
                ("a missing field", lambda d: d["projects"][0].pop("blurb")),
                ("an extra field", lambda d: d["projects"][0].update(lock=True)),
                ("a wrong type", lambda d: d["projects"][1]["detail"].update(features="x")),
                ("pending as text", lambda d: d.update(pending="2")),
                ("a duplicate slug", lambda d: d["projects"].append(copy.deepcopy(d["projects"][0]))),
                ("a chronicle entry without text", lambda d: d["chronicle"][0].pop("text")),
                ("an unknown state", lambda d: d["projects"][0].update(state="private")),
                ("an unknown access", lambda d: d["projects"][0].update(access="maybe")),
                ("a ring province not granted", lambda d: d["projects"][0].update(access="requested")),
                ("a ring province coming soon", lambda d: d["projects"][0].update(state="coming-soon")),
                ("an install link that is not https", lambda d: d["projects"][0].update(install="itms://x")),
                ("an admin with addable", lambda d: d["addable"].append(copy.deepcopy(d["projects"][0])))]:
            with self.subTest(label):
                self.assertNotEqual(self.broken(change), [])
        self.assertEqual(self.broken(lambda d: d.update(pending=None)), [])

    def test_catches_a_wrong_addable(self):
        with samples.fake_world():
            new = server.empire_data(samples.ACCOUNTS["sample-new-member-token"], "sample-new-member-token", IP)
        self.assertEqual(samples.check_empire(new), [])
        for label, change in [
                ("an install link in addable", lambda d: d["addable"][1].update(install="https://example.com/x")),
                ("granted in addable", lambda d: d["addable"][1].update(access="granted")),
                ("a coming-soon app requested", lambda d: d["addable"][0].update(access="requested"))]:
            with self.subTest(label):
                data = copy.deepcopy(new)
                change(data)
                self.assertNotEqual(samples.check_empire(data), [])

    def test_error_and_decision_checks(self):
        self.assertEqual(samples.check_error({"error": "Please log in again.", "code": "unauthorized"}), [])
        self.assertNotEqual(samples.check_error({"error": "Please log in again."}), [])
        self.assertNotEqual(samples.check_error({"error": "x", "code": "unauthenticated"}), [])
        self.assertEqual(samples.check_decision({"ok": True, "approvals": None, "pending": None}), [])
        self.assertNotEqual(samples.check_decision({"ok": True, "approvals": [], "pending": 1}), [])
        self.assertNotEqual(samples.check_decision({"ok": True}), [])


if __name__ == "__main__":
    unittest.main()
