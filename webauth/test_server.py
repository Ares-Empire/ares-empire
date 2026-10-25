"""Hub contract tests: in-memory HTTP requests, fake PocketBase, no external network."""
import copy
import http.client
import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from webauth import server


class Socket:
    def __init__(self, request):
        self.input = io.BytesIO(request)
        self.output = io.BytesIO()

    def makefile(self, *args):
        return self.input

    def sendall(self, body):
        self.output.write(body)


class Pulse(io.BytesIO):
    status = 200

    def __init__(self, body):
        super().__init__(json.dumps(body).encode())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class HubTests(unittest.TestCase):
    def setUp(self):
        server._cache.clear()
        server._live_cache.clear()
        self.records = {
            'user-one': {'id': 'userone00000001', 'name': 'First', 'admin': False,
                         'approved': True, 'services': ['empire'], 'ring': ['aresium', 'private', 'unknown']},
            'user-two': {'id': 'usertwo00000002', 'name': 'Second', 'admin': False,
                         'approved': True, 'services': ['empire'], 'ring': []},
            'admin-one': {'id': 'adminone0000001', 'name': 'Admin', 'admin': True,
                          'approved': True, 'services': ['empire'], 'ring': []},
        }
        # Waiting for Patrik: a new sign-up, and an approved account asking for two more apps.
        self.pending = [{'id': 'pending00000001', 'name': 'New', 'email': 'new@example.com',
                         'created': '2026-10-24 12:00:00Z', 'approved': False, 'admin': False,
                         'requested': ['arestemis']},
                        {'id': 'asking000000002', 'name': 'Member', 'email': 'member@example.com',
                         'created': '2026-10-24 13:00:00Z', 'approved': True, 'admin': False,
                         'requested': ['aresium', 'aresus']}]
        self.calls = []
        self.state = {
            'projects': [self.province(slug) for slug in ('aresium', 'other', 'private')],
            'ideas': [{'title': 'Expansion', 'note': 'A plan'}],
            'chronicle': [{'project': p, 'text': p, 'at': '2026-10-24'}
                          for p in ('aresium', 'other', 'private', 'unknown', 'empire')],
        }
        self.catalog = {'aresium': {'users': 'coming-soon'}, 'other': {'users': 'open'}}
        self.enterContext(patch.object(server, 'pb_call', side_effect=self.pb))
        self.real_load_state = server.load_state
        self.enterContext(patch.object(server, 'load_state', side_effect=lambda: copy.deepcopy(self.state)))
        self.enterContext(patch.object(server, 'load_catalog', side_effect=lambda: copy.deepcopy(self.catalog)))
        self.pulse = self.enterContext(patch.object(server.urllib.request, 'urlopen', side_effect=OSError('no pulse')))
        self.enterContext(patch.object(server.Handler, 'log_message'))

    @staticmethod
    def province(slug):
        return {'slug': slug, 'name': slug.title(), 'url': 'https://' + slug + '.example.com',
                'logo': 'brand/test.png', 'status': 'CONQUERED', 'domain': slug + '.example.com',
                'blurb': 'Fixture', 'detail': {'about': 'About', 'features': ['One'], 'setup': '',
                                             'wip': [], 'ideas': [], 'changelog': []}}

    def pb(self, path, body=None, token=None, client_ip=None, method='POST'):
        self.calls.append((path, copy.deepcopy(body), token, client_ip, method))
        if path.endswith('/auth-refresh'):
            if token not in self.records:
                return 400, {}
            return 200, {'record': copy.deepcopy(self.records[token])}
        if path.startswith('/api/collections/users/records?'):
            query = parse_qs(urlparse(path).query)
            self.assertEqual(query['filter'], ['approved = false || requested:length > 0'])
            self.assertEqual(query['fields'], ['id,email,name,created,requested,approved'])
            return 200, {'items': copy.deepcopy(self.pending), 'totalItems': len(self.pending), 'totalPages': 1}
        record_path, _, query = path.partition('?')
        account_id = record_path.rsplit('/', 1)[1]
        account = next((p for p in self.pending if p['id'] == account_id), None)
        if method == 'PATCH' and body is not None and set(body) == {'ring'}:
            self.assertEqual(account_id, self.records[token]['id'])
            self.records[token]['ring'] = body['ring'][:]
            return 200, copy.deepcopy(self.records[token])
        self.assertTrue(self.records[token]['admin'])
        if method == 'GET':
            self.assertEqual(parse_qs(query), {'fields': ['id,approved,requested']})
            return (200, {k: account[k] for k in ('id', 'approved', 'requested')}) if account else (404, {})
        if method == 'PATCH':
            # Approve adds exactly the listed requests; decline (of an approved account) removes exactly them.
            self.assertIn(body, ({'approved': True, 'services+': account['requested']},
                                 {'requested-': account['requested']}))
            if 'requested-' in body:
                self.assertTrue(account['approved'])
            self.pending = [p for p in self.pending if p['id'] != account_id]
            return 200, {'id': account_id}
        if method == 'DELETE':
            self.assertFalse(account['approved'])
            self.pending = [p for p in self.pending if p['id'] != account_id]
            return 204, {}
        raise AssertionError((path, body, token, method))

    def request(self, path='/api/empire', token='user-one', method='GET', body=None,
                headers=None, raw=None):
        request_headers = {'Host': 'hub.example.com', 'X-Forwarded-For': '192.0.2.5, 192.0.2.10'}
        if token is not None:
            request_headers['Authorization'] = 'Bearer ' + token
        if headers:
            request_headers.update(headers)
        payload = raw if raw is not None else (json.dumps(body).encode() if body is not None else b'')
        if payload:
            request_headers.setdefault('Content-Length', str(len(payload)))
            request_headers.setdefault('Content-Type', 'application/json')
        head = f'{method} {path} HTTP/1.0\r\n' + ''.join(f'{k}: {v}\r\n' for k, v in request_headers.items())
        sock = Socket(head.encode() + b'\r\n' + payload)
        server.Handler(sock, ('127.0.0.1', 1234), object())
        response_head, response_body = sock.output.getvalue().split(b'\r\n\r\n', 1)
        status = int(response_head.split(b' ', 2)[1])
        response_headers = dict(line.decode().split(': ', 1) for line in response_head.split(b'\r\n')[1:])
        data = json.loads(response_body) if response_body and 'application/json' in response_headers.get('Content-Type', '') else response_body
        return status, data, response_headers

    def test_user_filtering_and_version_one_fields(self):
        status, data, headers = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(data['version'], 2)
        self.assertEqual(data['me'], {'id': 'userone00000001', 'name': 'First', 'admin': False})
        self.assertEqual([p['slug'] for p in data['projects']], ['aresium'])
        self.assertEqual([p['slug'] for p in data['addable']], ['other'])
        self.assertEqual([e['project'] for e in data['chronicle']], ['aresium'])
        self.assertEqual(data['ideas'], [])
        self.assertEqual(data['pending'], 0)
        self.assertEqual(data['projects'][0]['state'], 'coming-soon')
        self.assertEqual(data['projects'][0]['app'], 'aresium://')
        self.assertEqual(data['projects'][0]['detail'], self.state['projects'][0]['detail'])
        self.assertIsNone(data['addable'][0]['app'])
        self.assertEqual(data['addable'][0]['state'], 'open')
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(self.calls[0][2:4], ('user-one', '192.0.2.10'))
        self.assertEqual(len(self.calls), 1)  # Users never ask PocketBase for approval metadata.

    def test_accept_language_parsing_through_hub_api(self):
        for header, expected in ((None, 'en'), ('de', 'de'), ('de-DE', 'de'),
                                 ('de-DE,de;q=0.9,en;q=0.8', 'de'), ('en', 'en'),
                                 ('en-GB,de;q=0.5', 'en'), ('fr', 'en'), ('broken', 'en'),
                                 ('fr,de;q=0.8,en;q=0.9', 'en'), ('de;q=0.8,en;q=0.8', 'de'),
                                 ('en;q=0.8,de;q=0.8', 'en'), ('de;q=0', 'en'),
                                 ('de;q=oops', 'en'), ('de;q=1.1', 'en'), ('de;q=-1', 'en'),
                                 ('de;q=NaN', 'en'), ('DE-de;Q=0.9,en;q=0.8', 'de')):
            with self.subTest(header=header):
                status, data, headers = self.request(token=None,
                    headers={'Accept-Language': header} if header is not None else {})
                self.assertEqual((status, data), (401, {'error': 'unauthenticated'}))
                self.assertEqual(headers['Content-Language'], expected)

    def test_live_languages_are_forwarded_and_cached_per_account_and_language(self):
        def answer(request, timeout):
            language = request.get_header('Accept-language')
            self.assertIn(language, ('en', 'de'))
            self.assertEqual(timeout, 2)
            if request.full_url == server.ARESUS_OVERVIEW_URL:
                line = 'Server ausgefallen seit 04:53' if language == 'de' else 'Server down since 04:53'
                return Pulse({'provinces': [{'slug': 'private', 'state': 'issue', 'line': line},
                                            {'slug': 'other', 'state': 'active', 'line': 'Website 5 ms'}]})
            return Pulse({'line': '12 € im Oktober ausgegeben' if language == 'de' else '€12 spent in October'})
        self.pulse.side_effect = answer
        for _ in range(2):
            for language, spending, issue in (('de', '12 € im Oktober ausgegeben', 'Problem: Server ausgefallen seit 04:53'),
                                               ('en', '€12 spent in October', 'Issue: Server down since 04:53')):
                status, data, headers = self.request(token='admin-one', headers={'Accept-Language': language})
                self.assertEqual(status, 200)
                self.assertEqual(headers['Content-Language'], language)
                live = {p['slug']: p['live'] for p in data['projects']}
                self.assertEqual(live, {'aresium': spending, 'other': 'Website 5 ms', 'private': issue})
                self.assertEqual(data['ideas'], self.state['ideas'])
                self.assertEqual(data['chronicle'], self.state['chronicle'])
                self.assertEqual(data['projects'][0]['blurb'], 'Fixture')
                self.assertEqual(data['projects'][0]['detail'], self.state['projects'][0]['detail'])
        self.assertEqual(self.pulse.call_count, 4)  # One pulse and overview per language, shared across provinces.
        self.request(headers={'Accept-Language': 'de'})
        self.assertEqual(self.pulse.call_count, 6)  # A second account cannot reuse the admin's lines.
        with patch.object(server, 'time', return_value=server.time() + 61):
            self.request(token='admin-one', headers={'Accept-Language': 'de'})
        self.assertEqual(self.pulse.call_count, 8)

    def test_ring_response_uses_request_language(self):
        self.pulse.side_effect = lambda request, **kw: Pulse({'line': request.get_header('Accept-language')})
        status, data, headers = self.request('/api/empire/ring', method='POST', body={'add': 'aresium'},
                                             headers={'Accept-Language': 'de'})
        self.assertEqual(status, 200)
        self.assertEqual(data['projects'][0]['live'], 'de')
        self.assertEqual(headers['Content-Language'], 'de')

    def test_auth_errors_are_translated_when_read_from_the_cache(self):
        for upstream, status, english, german in (
                (403, 403, 'This account has no access to Ares Empire.',
                 'Dieses Konto hat keinen Zugang zu Ares Empire.'),
                (0, 503, 'Login service unavailable, try again in a minute.',
                 'Anmeldedienst nicht erreichbar, versuch es in einer Minute noch einmal.')):
            server._cache.clear()
            with patch.object(server, 'pb_call', return_value=(upstream, {})):
                for language, expected in (('en', english), ('de', german)):
                    with self.subTest(upstream=upstream, language=language):
                        result, data, headers = self.request(headers={'Accept-Language': language})
                        self.assertEqual((result, data), (status, {'error': expected}))
                        self.assertEqual(headers['Content-Language'], language)

    def test_account_action_errors_follow_request_language(self):
        self.request()  # Prime authentication; below only the account write is faked.
        for upstream, status, english, german in (
                (400, 400, 'Invalid account request.', 'Ungültige Kontoanfrage.'),
                (401, 401, 'unauthenticated', 'unauthenticated'),
                (403, 403, 'Forbidden.', 'Kein Zugang.'),
                (404, 404, 'Account not found.', 'Konto nicht gefunden.'),
                (0, 503, 'Account service unavailable, try again in a minute.',
                 'Kontodienst nicht erreichbar, versuch es in einer Minute noch einmal.'),
                (200, 503, 'Account service returned an unreadable response.',
                 'Die Antwort des Kontodienstes ist nicht lesbar.')):
            with patch.object(server, 'pb_call', return_value=(upstream, {})):
                for language, expected in (('en', english), ('de', german)):
                    with self.subTest(upstream=upstream, language=language):
                        result, data, headers = self.request('/api/empire/ring', method='POST', body={'add': 'other'},
                                                             headers={'Accept-Language': language})
                        self.assertEqual((result, data), (status, {'error': expected}))
                        self.assertEqual(headers['Content-Language'], language)

    def test_missing_state_and_admin_errors_follow_request_language(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory, \
                patch.object(server, 'STATE_PATH', str(Path(directory) / 'missing.json')), \
                patch.object(server, 'load_state', side_effect=self.real_load_state):
            for language, expected in (('en', 'Hub data unavailable, try again in a minute.'),
                                       ('de', 'Hub-Daten nicht erreichbar, versuch es in einer Minute noch einmal.')):
                self.assertEqual(self.request(headers={'Accept-Language': language})[:2],
                                 (503, {'error': expected}))
        for language, expected in (('en', 'Administrator access required.'),
                                   ('de', 'Dafür brauchst du Administratorrechte.')):
            self.assertEqual(self.request('/api/empire/approvals', headers={'Accept-Language': language})[:2],
                             (403, {'error': expected}))

    def test_german_browser_still_gets_english_login_pages(self):
        for path, phrase in (('/login', 'One account for every service'), ('/login/email', 'Log in'),
                              ('/signup', 'Create'), ('/forgot', 'Reset')):
            with self.subTest(path=path):
                status, body, headers = self.request(path, token=None, headers={'Accept-Language': 'de'})
                self.assertEqual(status, 200)
                self.assertEqual(headers['Content-Language'], 'en')
                self.assertIn(phrase.lower().encode(), body.lower())
        with patch.object(server, 'pb_call', return_value=(200, {'record': {'id': 'unapproved'}})):
            status, body, headers = self.request('/login', token=None, method='POST',
                raw=b'email=fixture%40example.com&password=fixture-password', headers={'Accept-Language': 'de'})
            self.assertEqual(status, 503)  # Malformed login stays English, too.
            self.assertEqual(headers['Content-Language'], 'en')
            self.assertIn(b'Login is unavailable right now.', body)

    def test_accounts_and_cached_records_are_isolated(self):
        first = self.request()[1]
        second = self.request(token='user-two')[1]
        self.assertEqual(first['me']['name'], 'First')
        self.assertEqual(second['me']['name'], 'Second')
        self.assertEqual(second['projects'], [])
        self.assertEqual(second['chronicle'], [])
        self.assertEqual([p['slug'] for p in second['addable']], ['aresium', 'other'])
        self.request()
        self.assertEqual(len(self.calls), 2)
        self.assertNotIn('user-one', server._cache)

    def test_admin_sees_all_and_pending(self):
        status, data, _ = self.request(token='admin-one')
        self.assertEqual(status, 200)
        self.assertEqual([p['slug'] for p in data['projects']], ['aresium', 'other', 'private'])
        self.assertTrue(all(p['state'] == 'open' for p in data['projects']))
        self.assertEqual(data['ideas'], self.state['ideas'])
        self.assertEqual(data['chronicle'], self.state['chronicle'])
        self.assertEqual(data['addable'], [])
        self.assertEqual(data['pending'], 2)
        self.assertEqual(self.calls[-1][2:], ('admin-one', '192.0.2.10', 'GET'))

    def test_cookie_and_bearer_use_same_auth(self):
        status, data, _ = self.request(token=None, headers={'Cookie': server.COOKIE_NAME + '=user-one'})
        self.assertEqual(status, 200)
        self.assertEqual(data['me']['id'], self.records['user-one']['id'])
        self.assertEqual(self.request(headers={'Authorization': 'bEaReR user-one'})[0], 200)
        # An explicit malformed/rejected Authorization header cannot fall back to a cookie.
        self.assertEqual(self.request(headers={'Authorization': 'Basic user-one',
                         'Cookie': server.COOKIE_NAME + '=user-one'})[0], 401)

    def test_auth_status_mapping(self):
        for upstream, expected in [(400, 401), (401, 401), (403, 403), (0, 503),
                                   (429, 503), (500, 503), (502, 503), (302, 503), (404, 503)]:
            with self.subTest(upstream=upstream):
                server._cache.clear()
                with patch.object(server, 'pb_call', return_value=(upstream, {})) as pb:
                    for _ in range(2):
                        status, data, _ = self.request()
                        self.assertEqual(status, expected)
                        self.assertIn('error', data)
                    self.assertEqual(pb.call_count, 2 if expected == 503 else 1)
        self.assertEqual(self.request(token=None)[0], 401)

    def test_missing_service_or_approval_is_forbidden(self):
        for change in ({'services': []}, {'services': 'empire'}, {'approved': False}):
            with self.subTest(change=change):
                record = {**self.records['user-one'], **change}
                server._cache.clear()
                with patch.object(server, 'pb_call', return_value=(200, {'record': record})):
                    self.assertEqual(self.request()[0], 403)

    def test_malformed_refresh_is_uncached_unavailable(self):
        for data in ({}, {'record': None}, {'record': []}, {'record': {}}, {'record': {'id': 123}}):
            with self.subTest(data=data), patch.object(server, 'pb_call', return_value=(200, data)) as pb:
                server._cache.clear()
                self.assertEqual(self.request()[0], 503)
                self.assertEqual(self.request()[0], 503)
                self.assertEqual(pb.call_count, 2)
                self.assertEqual(server._cache, {})

    def test_web_outage_and_forbidden_preserve_status(self):
        for upstream, expected in ((0, 503), (403, 403)):
            with self.subTest(upstream=upstream), patch.object(server, 'pb_call', return_value=(upstream, {})):
                server._cache.clear()
                status, _, headers = self.request('/', token=None, headers={'Cookie': server.COOKIE_NAME + '=user-one'})
                self.assertEqual(status, expected)
                self.assertNotIn('Location', headers)
                self.assertNotIn('Set-Cookie', headers)

    def test_login_preserves_auth_statuses_and_forwards_ip(self):
        for upstream, expected in ((400, 401), (401, 401), (403, 403), (429, 503), (0, 503), (500, 503)):
            with self.subTest(upstream=upstream), patch.object(server, 'pb_call', return_value=(upstream, {})) as pb:
                status, _, headers = self.request('/login', token=None, method='POST',
                    raw=b'email=fixture%40example.com&password=fixture-password',
                    headers={'Content-Type': 'application/x-www-form-urlencoded'})
                self.assertEqual(status, expected)
                self.assertNotIn('Set-Cookie', headers)
                self.assertEqual(pb.call_args.kwargs['client_ip'], '192.0.2.10')
        with patch.object(server, 'pb_call', return_value=(200, {'token': 'user-one', 'record': self.records['user-one']})):
            status, _, headers = self.request('/login', token=None, method='POST',
                raw=b'email=fixture%40example.com&password=fixture-password',
                headers={'Content-Type': 'application/x-www-form-urlencoded'})
            self.assertEqual(status, 303)
            self.assertEqual(headers['Location'], '/')
            self.assertIn('empire_session=user-one', headers['Set-Cookie'])

    def test_login_malformed_success_is_unavailable(self):
        for data in ({}, {'token': 'x'}, {'token': 1, 'record': self.records['user-one']},
                     {'token': 'x', 'record': {'id': ''}}):
            with self.subTest(data=data), patch.object(server, 'pb_call', return_value=(200, data)):
                self.assertEqual(server.login('fixture@example.com', 'password', '192.0.2.10')[2], 503)

    def test_ring_add_remove_and_cache_invalidation(self):
        self.request()  # Prime the cached refresh with the old ring.
        status, data, _ = self.request('/api/empire/ring', method='POST', body={'add': 'other'})
        self.assertEqual(status, 200)
        self.assertEqual([p['slug'] for p in data['projects']], ['aresium', 'other'])
        self.assertEqual(data['addable'], [])
        self.assertEqual(self.calls[-1][1:], ({'ring': ['aresium', 'private', 'unknown', 'other']},
                         'user-one', '192.0.2.10', 'PATCH'))
        self.assertEqual([p['slug'] for p in self.request()[1]['projects']], ['aresium', 'other'])
        self.assertEqual(self.request('/api/empire/ring', method='POST', body={'add': 'other'})[0], 200)
        self.assertEqual(self.records['user-one']['ring'].count('other'), 1)
        status, data, _ = self.request('/api/empire/ring', method='POST', body={'remove': 'aresium'})
        self.assertEqual(status, 200)
        self.assertEqual([p['slug'] for p in data['projects']], ['other'])
        self.assertEqual([e['project'] for e in data['chronicle']], ['other'])
        self.assertEqual([p['slug'] for p in self.request()[1]['projects']], ['other'])
        self.assertEqual(self.request('/api/empire/ring', method='POST', body={'remove': 'aresium'})[0], 200)

    def test_ring_refuses_invalid_actions_without_writing(self):
        for body in ({'add': 'private'}, {'add': 'unknown'}, {'remove': 'private'}, {'add': []},
                     {'add': 'aresium', 'remove': 'other'}, {}, {'approve': True}):
            with self.subTest(body=body):
                self.assertEqual(self.request('/api/empire/ring', method='POST', body=body)[0], 400)
        self.assertTrue(all(call[-1] == 'POST' and call[0].endswith('/auth-refresh') for call in self.calls))

    def test_ring_accepts_cookie_and_uses_that_token(self):
        status, data, _ = self.request('/api/empire/ring', token=None, method='POST',
                                      body={'add': 'aresium'}, headers={'Cookie': server.COOKIE_NAME + '=user-two'})
        self.assertEqual(status, 200)
        self.assertEqual([p['slug'] for p in data['projects']], ['aresium'])
        self.assertEqual(self.calls[-1][2], 'user-two')

    def test_approvals_are_admin_only(self):
        for method, path, body in [('GET', '/api/empire/approvals', None),
                                  ('POST', '/api/empire/approvals/pending00000001', {'approve': True}),
                                  ('POST', '/api/empire/approvals/pending00000001', {'decline': True})]:
            with self.subTest(method=method, body=body):
                status, data, _ = self.request(path, method=method, body=body)
                self.assertEqual(status, 403)
                self.assertIn('error', data)
        self.assertEqual(len(self.calls), 1)

    def test_approvals_list_shape_and_caller_token(self):
        status, data, _ = self.request('/api/empire/approvals', token='admin-one')
        self.assertEqual(status, 200)
        self.assertEqual(data, [
            {'id': 'pending00000001', 'email': 'new@example.com', 'name': 'New', 'created': '2026-10-24 12:00:00Z',
             'requested': ['arestemis'], 'approved': False},
            {'id': 'asking000000002', 'email': 'member@example.com', 'name': 'Member',
             'created': '2026-10-24 13:00:00Z', 'requested': ['aresium', 'aresus'], 'approved': True}])
        self.assertEqual(self.calls[-1][2:], ('admin-one', '192.0.2.10', 'GET'))

    def test_approvals_list_reads_unexpected_values_safely(self):
        def pb(path, **kwargs):
            return 200, {'items': [{'id': 'x', 'requested': 'arestemis', 'approved': 'yes'},
                                   {'id': 'y', 'requested': ['aresium', 3, None], 'approved': True}],
                         'totalItems': 2, 'totalPages': 1}
        with patch.object(server, 'pb_call', side_effect=pb):
            items = server.pending_accounts('admin-one', '192.0.2.10')
        self.assertEqual([(i['requested'], i['approved']) for i in items], [([], False), (['aresium'], True)])

    def test_approvals_pagination(self):
        def pb(path, **kwargs):
            page = int(parse_qs(urlparse(path).query)['page'][0])
            return 200, {'items': [{'id': str(page)}], 'totalItems': 2, 'totalPages': 2}
        with patch.object(server, 'pb_call', side_effect=pb):
            self.assertEqual([r['id'] for r in server.pending_accounts('admin-one', '192.0.2.10')], ['1', '2'])

    def test_approve_and_decline_use_caller_token(self):
        cases = [('pending00000001', 'approve', 'PATCH', {'approved': True, 'services+': ['arestemis']}),
                 ('pending00000001', 'decline', 'DELETE', None),
                 ('asking000000002', 'approve', 'PATCH', {'approved': True, 'services+': ['aresium', 'aresus']}),
                 ('asking000000002', 'decline', 'PATCH', {'requested-': ['aresium', 'aresus']})]
        waiting = copy.deepcopy(self.pending)
        for account_id, action, method, sent in cases:
            with self.subTest(account=account_id, action=action):
                self.pending = copy.deepcopy(waiting)
                status, data, _ = self.request('/api/empire/approvals/' + account_id, token='admin-one',
                                              method='POST', body={action: True})
                self.assertEqual(status, 200)
                self.assertEqual(data, {'ok': True})
                # First the account's current state, then the one write, both with the admin's own token.
                self.assertEqual(self.calls[-2][0], '/api/collections/users/records/' + account_id +
                                 '?fields=id%2Capproved%2Crequested')
                self.assertEqual(self.calls[-2][2:], ('admin-one', '192.0.2.10', 'GET'))
                self.assertEqual(self.calls[-1][2:], ('admin-one', '192.0.2.10', method))
                self.assertEqual(self.calls[-1][1], sent)
                self.assertNotIn(account_id, [p['id'] for p in self.pending])

    def test_approval_of_an_unknown_or_unreadable_account(self):
        self.request(token='admin-one')
        self.assertEqual(self.request('/api/empire/approvals/missing00000003', token='admin-one',
                                      method='POST', body={'approve': True})[0], 404)
        self.assertEqual(self.calls[-1][4], 'GET')  # nothing written
        with patch.object(server, 'pb_call', return_value=(200, {'id': 'someoneelse0004'})):
            self.assertEqual(self.request('/api/empire/approvals/pending00000001', token='admin-one',
                                          method='POST', body={'approve': True})[0], 503)

    def test_website_signup_asks_for_the_hub_in_english(self):
        with patch.object(server, 'pb_call', return_value=(200, {'id': 'signup000000001'})) as pb:
            self.assertEqual(server.signup('new@example.com', 'Fictional-pass1', 'Fictional-pass1', '192.0.2.10'), '')
        self.assertEqual(pb.call_args_list[0].args, ('/api/collections/users/records', {
            'email': 'new@example.com', 'password': 'Fictional-pass1', 'passwordConfirm': 'Fictional-pass1',
            'requested': ['empire'], 'language': 'en'}))
        self.assertEqual(pb.call_args_list[1].args[0], '/api/collections/users/request-verification')

    def test_approval_action_validation(self):
        for body in ({'approve': False}, {'approve': 1}, {'decline': 1}, {},
                     {'approve': True, 'decline': True}, {'admin': True}):
            with self.subTest(body=body):
                self.assertEqual(self.request('/api/empire/approvals/pending00000001', token='admin-one',
                                 method='POST', body=body)[0], 400)
        self.assertEqual(self.request('/api/empire/approvals/bad-id', token='admin-one',
                         method='POST', body={'approve': True})[0], 400)
        self.assertEqual(len(self.calls), 1)

    def test_approval_write_refusal_and_outage_are_returned(self):
        self.request(token='admin-one')  # Prime authentication before faking the write.
        for upstream, expected in ((403, 403), (404, 404), (0, 503), (500, 503)):
            with self.subTest(upstream=upstream), patch.object(server, 'pb_call', return_value=(upstream, {})):
                self.assertEqual(self.request('/api/empire/approvals/pending00000001', token='admin-one',
                    method='POST', body={'decline': True})[0], expected)

    def test_pocketbase_write_errors_and_outage(self):
        self.request()  # Use cached auth; only the mutation is faked below.
        for upstream, expected in ((0, 503), (429, 503), (500, 503), (401, 401), (403, 403), (404, 404)):
            with self.subTest(upstream=upstream), patch.object(server, 'pb_call', return_value=(upstream, {})):
                self.assertEqual(self.request('/api/empire/ring', method='POST', body={'add': 'other'})[0], expected)

    def aresium_pulse_calls(self):
        return [c for c in self.pulse.call_args_list if c.args[0].full_url == server.PULSE_URLS['aresium']]

    def aresium_pulses(self):
        return len(self.aresium_pulse_calls())

    def test_live_failure_is_null_and_cached_per_account(self):
        self.assertIsNone(self.request()[1]['projects'][0]['live'])
        self.request()
        self.assertEqual(self.aresium_pulses(), 1)
        self.request(token='user-two')  # Aresium in addable also has a live field.
        self.assertEqual(self.aresium_pulses(), 2)
        request = self.aresium_pulse_calls()[-1].args[0]
        self.assertEqual(request.full_url, 'https://aresium.de/api/pulse')
        self.assertEqual(request.get_header('Authorization'), 'Bearer user-two')
        self.assertEqual(self.aresium_pulse_calls()[-1].kwargs, {'timeout': 2})

    def test_live_success_and_expiry(self):
        self.pulse.side_effect = lambda *a, **kw: Pulse({'line': 'Nothing imported yet'})
        self.assertEqual(self.request()[1]['projects'][0]['live'], 'Nothing imported yet')
        self.request()
        self.assertEqual(self.aresium_pulses(), 1)
        with patch.object(server, 'time', return_value=server.time() + 61):
            self.request()
        self.assertEqual(self.aresium_pulses(), 2)

    def test_live_bad_json_or_shape_or_http_error_is_null(self):
        for response in (lambda: io.BytesIO(b'not json'), lambda: Pulse({'line': 12}),
                         lambda: Pulse([]), lambda: urllib.error.HTTPError('https://example.com', 404, '', {}, None)):
            server._live_cache.clear()
            result = response()
            with self.subTest(result=type(result).__name__):
                if isinstance(result, Exception):
                    self.pulse.side_effect = result
                else:
                    self.pulse.side_effect = None
                    self.pulse.return_value = result
                self.assertIsNone(self.request()[1]['projects'][0]['live'])

    def test_other_provinces_get_their_line_from_aresus(self):
        def answer(request, timeout):
            if request.full_url == server.ARESUS_OVERVIEW_URL:
                return Pulse({'provinces': [{'slug': 'other', 'state': 'active', 'line': 'Website 5 ms'},
                                            {'slug': 'private', 'state': 'issue', 'line': 'Server down since 04:53'},
                                            {'slug': 'aresium', 'state': 'active', 'line': 'Website 7 ms'}]})
            return Pulse({'line': '€12 spent in October'})
        self.pulse.side_effect = answer
        live = {p['slug']: p['live'] for p in self.request(token='admin-one')[1]['projects']}
        self.assertEqual(live, {'aresium': '€12 spent in October', 'other': 'Website 5 ms',
                                'private': 'Issue: Server down since 04:53'})
        self.request(token='admin-one')
        aresus_calls = [c for c in self.pulse.call_args_list if c.args[0].full_url == server.ARESUS_OVERVIEW_URL]
        self.assertEqual(len(aresus_calls), 1)  # one overview per account and minute, not one per province
        self.assertEqual(aresus_calls[0].args[0].get_header('Authorization'), 'Bearer admin-one')

    def test_no_aresus_access_means_no_line(self):
        self.pulse.side_effect = urllib.error.HTTPError(server.ARESUS_OVERVIEW_URL, 403, '', {}, None)
        live = {p['slug']: p['live'] for p in self.request(token='admin-one')[1]['projects']}
        self.assertEqual(live, {'aresium': None, 'other': None, 'private': None})

    def test_live_truncated_response_is_null(self):
        self.pulse.side_effect = http.client.IncompleteRead(b'partial')
        self.assertIsNone(self.request()[1]['projects'][0]['live'])

    def test_invalid_json_and_oversize_body(self):
        for raw, status in ((b'broken', 400), (b'[]', 400), (b'null', 400), (b'x' * 10001, 413)):
            with self.subTest(raw=raw[:10]):
                self.assertEqual(self.request('/api/empire/ring', method='POST', raw=raw)[0], status)

    def test_head_api_returns_no_body(self):
        status, data, headers = self.request(method='HEAD')
        self.assertEqual(status, 200)
        self.assertEqual(data, b'')
        self.assertGreater(int(headers['Content-Length']), 0)


class DataAndTransportTests(unittest.TestCase):
    def test_state_missing_or_broken_is_503_otherwise_loaded(self):
        # All test files stay in the worktree and are removed on exit.
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = Path(directory) / 'state.json'
            with patch.object(server, 'STATE_PATH', str(path)):
                with self.assertRaises(server.APIError) as missing:
                    server.load_state()
                self.assertEqual(missing.exception.status, 503)
                path.write_text('{broken')
                with self.assertRaises(server.APIError):
                    server.load_state()
                path.write_text(json.dumps({'projects': [], 'ideas': [], 'chronicle': []}))
                self.assertEqual(server.load_state()['projects'], [])

    def test_catalog_is_separate_and_matches_current_contract(self):
        self.assertEqual(server.load_catalog(), {'aresium': {'users': 'coming-soon'}})
        self.assertEqual(server.APP_SCHEMES, {'aresium': 'aresium://', 'arestemis': 'arestemis://', 'aresus': 'aresus://',
                                              'arestoteles': 'arestoteles://'})

    def test_pb_transport_methods_and_forwarded_ip(self):
        for method in ('POST', 'PATCH', 'GET', 'DELETE'):
            with self.subTest(method=method), patch.object(server.urllib.request, 'urlopen', return_value=Pulse({'id': 'fixture'})) as urlopen:
                status, data = server.pb_call('/api/collections/users/records', {'ring': ['aresium']},
                                              'caller-token', '192.0.2.10', method=method)
                self.assertEqual(status, 200)
                self.assertEqual(data, {'id': 'fixture'})
                request = urlopen.call_args.args[0]
                self.assertEqual(request.method, method)
                self.assertEqual(request.get_header('Authorization'), 'caller-token')
                self.assertEqual(request.get_header('X-forwarded-for'), '192.0.2.10')
                self.assertEqual(urlopen.call_args.kwargs, {'timeout': 5})
                self.assertEqual(request.data is None, method in ('GET', 'DELETE'))

    def test_pb_transport_unreadable_or_unreachable_is_unavailable(self):
        for response in (io.BytesIO(b'not json'), io.BytesIO(b'[]'), OSError('offline')):
            response.status = 200 if isinstance(response, io.BytesIO) else None
            with self.subTest(response=type(response).__name__), patch.object(server.urllib.request, 'urlopen') as urlopen:
                if isinstance(response, Exception):
                    urlopen.side_effect = response
                else:
                    urlopen.return_value = response
                self.assertEqual(server.pb_call('/api/collections/users/auth-refresh'), (0, {}))


if __name__ == '__main__':
    unittest.main()


class BrandImageTests(unittest.TestCase):
    def test_only_images_under_brand_pass_with_a_bearer_token(self):
        self.assertTrue(server.is_brand_image("/brand/hermes.webp"))
        self.assertTrue(server.is_brand_image("/brand/ares-bust.PNG"))
        for path in ("/brand/../index.html", "/brand/../app/app.jsx", "/brand/", "/index.html",
                     "/brand/notes.txt", "/brand//hermes.webp", "/app/brand/x.png"):
            self.assertFalse(server.is_brand_image(path), path)


if __name__ == "__main__":
    unittest.main()
