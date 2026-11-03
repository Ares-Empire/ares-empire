"""Owner-file contract, startup failures, rendering and the accounts hand-off."""

import html
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock, patch

from webauth import contact, legal, owner, server
from webauth.owner_fixture import DETAILS, OwnerTestCase

ROOT = Path(__file__).resolve().parents[1]
WEB = str(ROOT / "web")


class OwnerTests(OwnerTestCase):
    def test_default_path_belongs_to_the_process_user_and_override_wins(self):
        self.assertEqual(owner.owner_path(), self.owner_file)
        with patch.dict(os.environ):
            os.environ.pop("ARES_OWNER_FILE")
            with patch.object(Path, "home", return_value=self.owner_file.parent):
                self.assertEqual(owner.owner_path(), self.owner_file.parent / ".config/ares-empire/owner.json")

    def test_every_legal_and_contact_page_uses_the_fixture_without_placeholders(self):
        for path in legal.PAGES:
            with self.subTest(path=path):
                page = legal.render(path, WEB)[0].decode()
                for value in DETAILS.values():
                    self.assertIn(value, page)
                self.assertNotIn("{{OWNER_", page)
        for path in contact.PAGES:
            with self.subTest(path=path):
                page = contact.render(path, None, WEB)[0].decode()
                self.assertIn(DETAILS["name"], page)
                self.assertIn('href="mailto:' + DETAILS["email"] + '"', page)
                self.assertNotIn("{{OWNER_", page)

    def test_owner_values_are_escaped_in_html(self):
        values = {key: '<&"\'>' for key in DETAILS}
        self.owner_file.write_text(json.dumps(values))
        for page in (legal.render('/imprint', WEB)[0].decode(), contact.page('empire', 'en')):
            self.assertIn(html.escape(values['name']), page)
            self.assertNotIn(values['name'], page)
            self.assertNotIn('&amp;lt;', page)

    def test_startup_loads_once_before_opening_socket(self):
        def httpd(*args):
            self.owner_file.unlink()
            self.assertEqual(owner.get_owner(), DETAILS)
            self.assertIn(DETAILS['email'], contact.page('empire', 'en'))
            self.assertIn(DETAILS['street'], legal.render('/imprint', WEB)[0].decode())
            return fake_httpd

        fake_httpd = Mock()
        with patch.object(server, 'LimitedHTTPServer', side_effect=httpd), patch.object(server.sys, 'stderr'):
            server.main()
        fake_httpd.serve_forever.assert_called_once()

    def test_missing_and_invalid_files_stop_startup_and_never_echo_values(self):
        sensitive = 'PRIVATE_SENTINEL_DO_NOT_ECHO'
        cases = [None, '', '{' + sensitive, '[]', 'null',
                 json.dumps({**DETAILS, 'extra': sensitive}),
                 json.dumps({key: value for key, value in DETAILS.items() if key != 'city'}),
                 '{"name":"' + sensitive + '","name":"duplicate"}',
                 b'\xff']
        for key in DETAILS:
            for value in ('', '  \n', None, 42, [], {}):
                cases.append(json.dumps({**DETAILS, 'name': sensitive, key: value}))
        for contents in cases:
            with self.subTest(case=cases.index(contents)):
                if contents is None:
                    self.owner_file.unlink(missing_ok=True)
                elif isinstance(contents, bytes):
                    self.owner_file.write_bytes(contents)
                else:
                    self.owner_file.write_text(contents)
                result = subprocess.run([sys.executable, '-m', 'webauth.server'], cwd=ROOT,
                                        capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(str(self.owner_file), result.stderr)
                self.assertIn('Owner file', result.stderr)
                self.assertNotIn(sensitive, result.stdout + result.stderr)
                for value in DETAILS.values():
                    self.assertNotIn(value, result.stdout + result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def test_accounts_environment_contains_only_email_and_is_private(self):
        destination = self.owner_file.parent / 'owner.env'
        owner.write_accounts_environment(destination)
        self.assertEqual(destination.read_text(), 'ARES_OWNER_EMAIL="owner@example.org"\n')
        self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
        self.owner_file.unlink()
        with self.assertRaisesRegex(ValueError, 'Owner file'):
            owner.write_accounts_environment(destination)
        self.assertEqual(destination.read_text(), 'ARES_OWNER_EMAIL="owner@example.org"\n')
