"""The contact pages of the Ares Empire and Arestemis (webauth/contact.py), and the form they share with aresium.de
(web/shared/forms/): in-memory requests through the hub's handler, no network."""
import hashlib
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from webauth.owner_fixture import OwnerTestCase

from webauth import contact, legal, server
from webauth.test_server import RESOURCE, WEB, send

SHARED = WEB / 'shared' / 'forms'
LOOKS = {app.slug: WEB / app.look.lstrip('/') for app in contact.APPS.values()}
PROBLEMS = ['empty', 'long', 'noemail', 'email', 'many', 'offline', 'failed']
HOOKS = ['data-contact-form', 'data-topic-note', 'data-optional-mark', 'data-counter', 'data-language-link',
         'data-compose', 'data-label', 'data-sent-line="app"', 'data-sent-line="answer"', 'id="contact-sent"',
         'name="kind"', 'name="message"', 'name="email"', 'name="name"', 'name="website"', 'data-look-switch']


def pages():
    """Every contact page: (path, app, language, html) with its default topic."""
    for path, (app, language) in contact.PAGES.items():
        yield path, app.slug, language, contact.page(app.slug, language)


def visible_text(page: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', re.sub(r'<(script|style)[\s\S]*?</\1>', '', page)))


def count(text: str, part: str) -> int:
    return text.count(part)


def custom_properties(css: str, selector: str) -> dict[str, str]:
    """The custom properties a rule with exactly this selector sets."""
    block = re.search(re.escape(selector) + r'\s*\{([^}]*)\}', css)
    return dict(re.findall(r'(--[\w-]+)\s*:\s*([^;]+);', block[1])) if block else {}


class PageTests(OwnerTestCase):
    def test_the_paths_name_the_app_and_the_language(self):
        self.assertEqual({path: (app.slug, language) for path, (app, language) in contact.PAGES.items()}, {
            '/contact': ('empire', 'en'), '/kontakt': ('empire', 'de'),
            '/arestemis/contact': ('arestemis', 'en'), '/arestemis/kontakt': ('arestemis', 'de')})
        for path, app, language, page in pages():
            with self.subTest(path=path):
                self.assertIn(f'<html lang="{language}" data-theme="dark">', page)
                other = contact.APPS[app].paths['de' if language == 'en' else 'en']
                label = 'Deutsch' if language == 'en' else 'English'
                self.assertRegex(page, rf'<a class="lang" href="{other}\?topic=question"[^>]*data-language-link>{label}</a>')
                self.assertIn(f'<link rel="alternate" hreflang="{"de" if language == "en" else "en"}" href="{other}" />', page)

    def test_topic_picks_the_topic_anything_else_is_a_question(self):
        self.assertEqual(contact.topic_from('access'), 'access')
        self.assertEqual(contact.topic_from('idea'), 'idea')
        for value in (None, '', 'bogus', 'ACCESS', 'access ', '<script>'):
            self.assertEqual(contact.topic_from(value), 'question', value)
        for app in contact.APPS:
            page = contact.page(app, 'en', 'access')
            self.assertRegex(page, r'<option value="access" selected [^>]*data-optional>Get the app</option>')
            self.assertRegex(page, r'<textarea id="contact-message"[^>]*placeholder="Anything to add\? \(optional\)"\s+aria-describedby')
            self.assertIn('data-optional-mark>(optional)<', page)
            self.assertIn('The install link comes by email, to this address.', page)
            self.assertIn(f'href="{contact.APPS[app].paths["de"]}?topic=access"', page)
            german = contact.page(app, 'de', 'problem')
            self.assertRegex(german, r'<option value="problem" selected [^>]*>Problem</option>')
            self.assertIn('placeholder="Was ist passiert, und was hätte passieren sollen?" required', german)
            self.assertIn('data-optional-mark hidden>', german)

    def test_both_languages_have_every_topic_problem_and_hook_in_the_same_order(self):
        def shape(page):
            return re.sub(r'"[^"]*"', '""', re.sub(r'>[^<]*<', '><', page))
        for app in contact.APPS:
            english, german = contact.page(app, 'en'), contact.page(app, 'de')
            self.assertEqual(shape(english), shape(german), app)
            for page in (english, german):
                self.assertEqual(re.findall(r'<option value="(\w+)"', page), list(contact.TOPICS))
                self.assertEqual(re.findall(r'data-problem="(\w+)"', page), PROBLEMS)
                self.assertEqual(count(page, 'data-optional>'), 1)   # only asking for the app needs no message
            for word in ('Get the app', 'Topic', 'Message', 'Answer to', 'Email', 'Send', 'Something else', 'Privacy',
                         'Imprint', 'Light appearance', 'Back to'):
                self.assertNotRegex(visible_text(german) + ' '.join(re.findall(r'(?:placeholder|data-\w+|aria-label)="([^"]*)"', german)),
                                    rf'\b{word}\b', f'{app}: {word}')

    def test_every_hook_the_scripts_look_for_is_on_the_page_once(self):
        script = (SHARED / 'contact-form.js').read_text(encoding='utf-8')
        look = (WEB / 'contact' / 'appearance.js').read_text(encoding='utf-8')
        for path, _, _, page in pages():
            for hook in HOOKS:
                with self.subTest(path=path, hook=hook):
                    self.assertEqual(count(page, f' {hook}'), 1)
            self.assertIn('data-sent="contact-sent"', page)
            self.assertRegex(page, r'data-sending="[^"]+" data-again="[^"]+"')
            self.assertRegex(page, r'data-sent-line="app" data-words="[^"]*%s[^"]*"')
            self.assertRegex(page, r'data-counter data-words="[^"]*%1[^"]*%2[^"]*"')
            # the look switch: hidden until its script shows it, labelled in the page's language
            self.assertRegex(page, r'<button class="look" type="button" aria-pressed="false" aria-label="[^"]+" title="[^"]+" data-look-switch hidden>')
        for hook in ('[data-contact-form]', '[data-topic-note]', '[data-optional-mark]', '[data-counter]',
                     '[data-language-link]', '[data-compose]', '[data-label]', '[data-sent-line]', '[data-problem]',
                     '[data-topic-icon]'):
            self.assertIn(hook, script)
        for problem in PROBLEMS:
            self.assertIn(f'"{problem}"', script)
        self.assertIn('[data-look-switch]', look)

    def test_the_form_posts_to_the_contact_collection_as_its_app_with_the_honeypot(self):
        self.assertEqual(contact.CONTACT_ENDPOINT, 'https://auth.ares-empire.de/api/collections/contact/records')
        for path, app, language, page in pages():
            with self.subTest(path=path):
                self.assertIn(f'data-endpoint="{contact.CONTACT_ENDPOINT}" data-app="{app}"', page)
                self.assertIn(f'data-language="{language}"', page)
                self.assertRegex(page, r'<div class="trap" aria-hidden="true">[\s\S]*name="website" type="text" tabindex="-1"')
                self.assertRegex(page, r'<input id="contact-email" name="email" type="email"[^>]*required')
                self.assertRegex(page, r'<input id="contact-name" name="name" type="text"[^>]*maxlength="100"')
                self.assertIn('data-max="5000"', page)
        # the account server takes these apps (accounts/pb_migrations/1793700000_contact_app_kind.js)
        migration = (WEB.parent / 'accounts' / 'pb_migrations' / '1793700000_contact_app_kind.js').read_text()
        allowed = re.search(r'const APPS = \[([^\]]*)\]', migration)[1]
        kinds = re.search(r'const KINDS = \[([^\]]*)\]', migration)[1]
        for app in contact.APPS:
            self.assertIn(f'"{app}"', allowed)
        for topic in contact.TOPICS:
            self.assertIn(f'"{topic}"', kinds)

    def test_the_words_address_no_one(self):
        # Patrik, 2026-10-31: no "you"/"your", no "du"/"dein" or du-imperatives; also in what the script swaps in.
        for app in contact.APPS:
            for topic in contact.TOPICS:
                self.assertNotRegex(contact.page(app, 'en', topic), r'(?i)\b(you|your|yours|you\'re)\b')
                self.assertNotRegex(contact.page(app, 'de', topic),
                                    r'(?i)\b(du|dich|dir|dein\w*|frag|schreib|gib|versuch|sende|melde)\b')

    def test_the_privacy_policy_imprint_and_email_fallback_are_linked_in_the_pages_language(self):
        for path, app, language, page in pages():
            with self.subTest(path=path):
                privacy, imprint = ('/privacy', '/imprint') if language == 'en' else ('/datenschutz', '/impressum')
                self.assertEqual(count(page, f'<a href="{privacy}">'), 2)   # the note and the footer
                self.assertIn(f'<a href="{imprint}">', page)
                self.assertEqual(count(page, 'href="mailto:owner@example.org"'), 2)   # a failed send and <noscript>
                self.assertRegex(page, r'data-problem="failed" hidden>[\s\S]*?mailto:owner@example\.org[\s\S]*?</p>')

    def test_the_empire_page_leads_home_and_arestemis_has_no_page_of_its_own(self):
        empire, arestemis = contact.page('empire', 'en'), contact.page('arestemis', 'de')
        self.assertIn('<a class="home" href="/"><img src="/brand/ares-bust-icon.png"', empire)
        self.assertIn('<a class="back" href="/">Back to Ares Empire</a>', empire)
        self.assertIn('<span class="home"><img src="/brand/artemis-icon.png"', arestemis)
        self.assertNotIn('class="back"', arestemis)
        self.assertIn('<div class="band" aria-hidden="true"><span>A</span><span>R</span><span>E</span><span>S</span>'
                      '<span class="space"></span><span>E</span>', empire)
        self.assertIn('>S</span></div>', arestemis)


class StyleTests(OwnerTestCase):
    def test_no_inline_code_nothing_from_other_hosts_and_a_strict_policy(self):
        for path, _, _, page in pages():
            with self.subTest(path=path):
                self.assertNotRegex(page, r'<(?:script|img|link|iframe|source)\b[^>]*\s(?:src|href)="(?:https?:)?//')
                self.assertNotRegex(page, r'\sstyle="|<style|<script>|\son\w+="')
        self.assertIn("default-src 'none'", contact.CSP)
        self.assertIn('connect-src https://auth.ares-empire.de;', contact.CSP)
        self.assertIn("form-action 'none'", contact.CSP)
        self.assertNotRegex(contact.CSP, r'unsafe|\*')
        for script in (SHARED / 'contact-form.js', WEB / 'contact' / 'appearance.js'):
            self.assertNotRegex(script.read_text(encoding='utf-8'), r'https?://', script.name)

    def test_every_file_a_page_loads_is_there_and_open(self):
        loaded = set()
        for path, _, _, page in pages():
            # what the page loads; its <link rel="alternate"> names the other language's page, which it does not load
            loaded |= {url for url in (a or b for a, b in RESOURCE.findall(page))} - set(contact.PAGES)
        css_urls = set()
        for name in ('shared/forms/contact-form.css', 'contact/hub.css', 'contact/empire.css', 'contact/arestemis.css',
                     'fonts/fonts.css'):
            for url in re.findall(r'url\(\s*["\']?([^"\')]+)', (WEB / name).read_text(encoding='utf-8')):
                css_urls.add(url if url.startswith('/') else '/fonts/' + url)
        css_urls.discard('/fonts/Cinzel-Variable.ttf')   # fonts.css names it; no contact page uses it
        self.assertEqual(loaded | css_urls, set(contact.ASSET_PATHS))
        self.assertLessEqual(contact.ASSET_PATHS, server.OPEN_PATHS)
        for url in contact.ASSET_PATHS:
            with self.subTest(url=url):
                self.assertTrue((WEB / url.lstrip('/')).is_file())
                with patch.object(server, 'WEB_ROOT', str(WEB)):
                    status, body, _ = send(url)
                self.assertEqual(status, 200)
                self.assertEqual(body, (WEB / url.lstrip('/')).read_bytes())

    def test_the_page_opens_dark_with_its_look_set_before_the_styles(self):
        for path, app, _, page in pages():
            with self.subTest(path=path):
                order = [page.index(part) for part in ('<script src="/contact/appearance.js"></script>',
                                                      'href="/shared/forms/contact-form.css"', 'href="/contact/hub.css"',
                                                      f'href="{contact.APPS[app].look}"')]
                self.assertEqual(order, sorted(order))
        for name in ('shared/forms/contact-form.css', 'contact/hub.css', 'contact/empire.css', 'contact/arestemis.css'):
            css = (WEB / name).read_text(encoding='utf-8')
            self.assertNotIn('prefers-color-scheme', css, name)   # the websites open dark, whatever the system says

    def test_every_look_sets_every_property_the_layout_uses_in_dark_and_light(self):
        used = set()
        for name in ('shared/forms/contact-form.css', 'contact/hub.css'):
            used |= set(re.findall(r'var\((--[\w-]+)', (WEB / name).read_text(encoding='utf-8')))
        used -= set(custom_properties((SHARED / 'contact-form.css').read_text(encoding='utf-8'), ':root'))
        self.assertIn('--highlight', used)
        for app, file in LOOKS.items():
            css = file.read_text(encoding='utf-8')
            dark, light = custom_properties(css, ':root'), custom_properties(css, 'html[data-theme="light"]')
            with self.subTest(look=app):
                self.assertEqual(used - set(dark), set())
                # light sets every property again, unless it is the same in both: a size, nothing (none), or another
                # property's value
                self.assertEqual({p for p, v in dark.items() if p not in light and p != '--band-size'
                                  and v != 'none' and not v.startswith('var(')}, set())

    def test_every_class_the_shared_layout_styles_is_on_every_page(self):
        css = re.sub(r'/\*[\s\S]*?\*/', '', (SHARED / 'contact-form.css').read_text(encoding='utf-8'))
        classes = set(re.findall(r'\.([a-z][\w-]*)', css)) - {'over', 'busy', 'visually-hidden'}   # the script's
        for path, app, _, page in pages():
            on_page = set(re.findall(r'class="([^"]+)"', page))
            on_page = {c for names in on_page for c in names.split()}
            missing = classes - on_page
            if contact.APPS[app].home is None:
                missing -= {'back'}   # no page to go back to
            if ' ' not in contact.APPS[app].band:
                missing -= {'space'}
            with self.subTest(path=path):
                self.assertEqual(missing, set())


class SharedFormTests(OwnerTestCase):
    """web/shared/forms/ is the original; aresium web/public/forms/ has byte-identical copies (README.md there)."""

    def sums(self) -> dict[str, str]:
        lines = (SHARED / 'SHA256SUMS').read_text(encoding='utf-8').splitlines()
        return {name: digest for digest, name in (line.split('  ') for line in lines if line)}

    def test_the_shared_files_match_their_hashes(self):
        sums = self.sums()
        self.assertEqual(set(sums), {'contact-form.js', 'contact-form.css'})
        for name, digest in sums.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((SHARED / name).read_bytes()).hexdigest(), digest,
                                 'changed? update SHA256SUMS and the copies (web/shared/forms/README.md)')

    def test_aresiums_copies_are_the_same_bytes(self):
        aresium = Path(os.environ.get('ARESIUM_DIR', WEB.parent.parent / 'aresium'))
        forms = aresium / 'web' / 'public' / 'forms'
        if not forms.is_dir():
            self.skipTest(f'no aresium checkout at {aresium}')
        for name in self.sums():
            with self.subTest(name=name):
                self.assertTrue((forms / name).is_file(), f'aresium has no copy of web/shared/forms/{name} at {forms}')
                self.assertEqual((forms / name).read_bytes(), (SHARED / name).read_bytes(),
                                 f'aresium {forms / name} differs from web/shared/forms/{name}')


class ServingTests(OwnerTestCase):
    """The pages through the hub's handler, on a web root whose privacy policies are published."""

    def setUp(self):
        super().setUp()
        server._cache.clear()
        self.enterContext(patch.object(server.Handler, 'log_message'))
        self.enterContext(patch.dict(os.environ, {'LEGAL_PREVIEW': ''}))
        record = {'id': 'userone00000001', 'approved': True, 'services': ['empire']}
        self.enterContext(patch.object(server, 'pb_call', return_value=(200, {'record': record})))
        directory = self.enterContext(tempfile.TemporaryDirectory(dir=Path(__file__).parent))
        self.root = Path(directory)
        (self.root / 'legal').mkdir()
        for entry in legal.PAGES.values():
            (self.root / 'legal' / entry.file).write_text(f'<h1>{entry.title}</h1><p>Approved text.</p>', encoding='utf-8')
        shutil.copy(WEB / 'legal' / 'page.html', self.root / 'legal')
        self.enterContext(patch.object(server, 'WEB_ROOT', str(self.root)))

    def test_every_page_is_open_in_its_language_with_its_policy(self):
        for path, (app, language) in contact.PAGES.items():
            for headers in ({}, {'Cookie': server.COOKIE_NAME + '=user-one'}, {'Accept-Language': 'de' if language == 'en' else 'en'}):
                with self.subTest(path=path, headers=headers):
                    status, body, answer = send(path, headers=headers)
                    self.assertEqual(status, 200)
                    self.assertEqual(answer['Content-Language'], language)
                    self.assertEqual(answer['Content-Security-Policy'], contact.CSP)
                    self.assertEqual(answer['Cache-Control'], 'no-store')
                    self.assertNotIn('Set-Cookie', answer)
                    self.assertIn(f'<html lang="{language}"', body.decode())
            status, body, answer = send(path, method='HEAD')
            self.assertEqual((status, body), (200, b''))
            self.assertEqual(answer['Content-Security-Policy'], contact.CSP)

    def test_topic_comes_from_the_address(self):
        page = send('/arestemis/contact?topic=access')[1].decode()
        self.assertRegex(page, r'<option value="access" selected ')
        page = send('/kontakt?topic=%3Cscript%3E')[1].decode()
        self.assertRegex(page, r'<option value="question" selected ')
        self.assertNotIn('<script>', page)

    def test_a_page_is_served_only_while_the_privacy_policy_in_its_language_is(self):
        (self.root / 'legal' / 'privacy.html').write_text('<h1>Privacy policy</h1><p>[ADDRESS]</p>', encoding='utf-8')
        self.assertEqual(send('/privacy')[0], 404)
        self.assertEqual((send('/contact')[0], send('/arestemis/contact')[0]), (404, 404))   # it collects data
        self.assertEqual((send('/kontakt')[0], send('/arestemis/kontakt')[0]), (200, 200))   # the German policy is out
        with patch.dict(os.environ, {'LEGAL_PREVIEW': '1'}):
            self.assertEqual(send('/contact')[0], 200)
        (self.root / 'legal' / 'datenschutz.html').unlink()
        self.assertEqual(send('/kontakt')[0], 404)

    def test_only_the_pages_themselves_are_open(self):
        for path in ('/contact/', '/arestemis', '/arestemis/', '/arestemis/contact/', '/arestemis/Contact',
                     '/contact.html', '/shared/forms/', '/shared/forms/README.md', '/shared/forms/SHA256SUMS',
                     '/contact/', '/contact/../index.html', '/legal/contact.js', '/legal/kontakt.html'):
            with self.subTest(path=path):
                status, _, headers = send(path)
                self.assertEqual(status, 303)
                self.assertEqual(headers['Location'], '/login')
        self.assertEqual(send('/contact', method='POST', raw=b'message=x',
                              headers={'Content-Type': 'application/x-www-form-urlencoded'})[0], 404)


if __name__ == '__main__':
    unittest.main()
