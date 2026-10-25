"""The fixture generator (tools/empire_samples.py): it runs, every file is the hub server's own answer, and the
contract checks catch what they should. Run from the repo root: python3 -m unittest tools/test_empire_samples.py"""
import copy
import json
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from tools import empire_samples as samples
from webauth import server

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
            "empire.admin.json", "empire.member.json", "empire.new-member.json", "approvals.json",
            "approval-decision.json", *(f"error.{code}.json" for code in server.ERROR_CODES)})

    def test_each_file_is_the_servers_answer(self):
        accounts = samples.ACCOUNTS
        with samples.fake_world():
            for name, token in (("empire.admin.json", "sample-admin-token"),
                                ("empire.member.json", "sample-member-token"),
                                ("empire.new-member.json", "sample-new-member-token")):
                with self.subTest(name=name):
                    self.assertEqual(self.files[name], server.empire_data(accounts[token], token, IP, "en"))
            approvals = server.pending_accounts("sample-admin-token", IP)
            self.assertEqual(self.files["approvals.json"], approvals)
            card = approvals[1]
            self.assertFalse(card["approved"])
            self.assertEqual(self.files["approval-decision.json"], server.decide_approval(
                card["id"], "sample-admin-token", IP, {"approve": True, "requested": card["requested"]}))

    def test_each_file_has_the_contracts_shape(self):
        for name, data in self.files.items():
            check = (samples.check_empire if name.startswith("empire.") else
                     samples.check_approvals if name == "approvals.json" else
                     samples.check_decision if name == "approval-decision.json" else samples.check_error)
            with self.subTest(name=name):
                self.assertEqual(check(data), [])
        for code in server.ERROR_CODES:
            self.assertEqual(self.files[f"error.{code}.json"]["code"], code)

    def test_the_three_accounts_see_what_the_contract_says(self):
        admin, member, new = (self.files[f"empire.{who}.json"] for who in ("admin", "member", "new-member"))
        seed = samples.read_seed()
        self.assertEqual([p["slug"] for p in admin["projects"]], [p["slug"] for p in seed["projects"]])
        self.assertEqual((len(admin["chronicle"]), len(admin["ideas"])), (len(seed["chronicle"]), len(seed["ideas"])))
        self.assertEqual(admin["pending"], len(self.files["approvals.json"]))
        self.assertTrue(all(p["state"] == "open" for p in admin["projects"]))
        self.assertEqual([p["slug"] for p in member["projects"]], ["aresium"])
        self.assertTrue(member["chronicle"] and all(e["project"] == "aresium" for e in member["chronicle"]))
        self.assertEqual((new["projects"], new["chronicle"], new["ideas"], new["pending"]), ([], [], [], 0))
        self.assertEqual([p["slug"] for p in new["addable"]], list(server.load_catalog()))
        self.assertEqual(sorted({a["verified"] for a in self.files["approvals.json"]}), [False, True])


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
                ("an unknown state", lambda d: d["projects"][0].update(state="private"))]:
            with self.subTest(label):
                self.assertNotEqual(self.broken(change), [])
        self.assertEqual(self.broken(lambda d: d.update(pending=None)), [])

    def test_error_and_decision_checks(self):
        self.assertEqual(samples.check_error({"error": "Please log in again.", "code": "unauthorized"}), [])
        self.assertNotEqual(samples.check_error({"error": "Please log in again."}), [])
        self.assertNotEqual(samples.check_error({"error": "x", "code": "unauthenticated"}), [])
        self.assertEqual(samples.check_decision({"ok": True, "approvals": None, "pending": None}), [])
        self.assertNotEqual(samples.check_decision({"ok": True, "approvals": [], "pending": 1}), [])
        self.assertNotEqual(samples.check_decision({"ok": True}), [])


if __name__ == "__main__":
    unittest.main()
