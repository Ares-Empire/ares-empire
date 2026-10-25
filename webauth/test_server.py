"""Hub contract tests: in-memory HTTP requests, fake PocketBase, no external network."""
import copy
import http.client
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import unittest
import urllib.error
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from webauth import legal, server


class Socket:
    def __init__(self, request):
        self.input = io.BytesIO(request)
        self.output = io.BytesIO()

    def makefile(self, *args):
        return self.input

    def sendall(self, body):
        self.output.write(body)


def send(path, token=None, method='GET', body=None, headers=None, raw=None):
    """One HTTP request through the hub's handler in memory: (status, JSON or body bytes, headers)."""
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
        self.pending = [{'id': 'pending00000001', 'name': 'New', 'email': 'new@example.com',
                         'created': '2026-10-24 12:00:00Z', 'approved': False, 'admin': False}]
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
            self.assertEqual(query['filter'], ['approved = false'])
            self.assertEqual(query['fields'], ['id,email,name,created'])
            return 200, {'items': copy.deepcopy(self.pending), 'totalItems': len(self.pending), 'totalPages': 1}
        account_id = path.rsplit('/', 1)[1]
        if method == 'PATCH' and body is not None and set(body) == {'ring'}:
            self.assertEqual(account_id, self.records[token]['id'])
            self.records[token]['ring'] = body['ring'][:]
            return 200, copy.deepcopy(self.records[token])
        if method == 'PATCH':
            self.assertTrue(self.records[token]['admin'])
            self.assertEqual(body, {'approved': True, 'services': ['empire']})
            self.pending = [p for p in self.pending if p['id'] != account_id]
            return 200, {'id': account_id, **body}
        if method == 'DELETE':
            self.assertTrue(self.records[token]['admin'])
            self.pending = [p for p in self.pending if p['id'] != account_id]
            return 204, {}
        raise AssertionError((path, body, token, method))

    def request(self, path='/api/empire', token='user-one', method='GET', body=None,
                headers=None, raw=None):
        return send(path, token, method, body, headers, raw)

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
        self.assertEqual(data['pending'], 1)
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
        self.assertEqual(data, [{k: v for k, v in self.pending[0].items() if k in ('id', 'email', 'name', 'created')}])
        self.assertEqual(self.calls[-1][2:], ('admin-one', '192.0.2.10', 'GET'))

    def test_approvals_pagination(self):
        def pb(path, **kwargs):
            page = int(parse_qs(urlparse(path).query)['page'][0])
            return 200, {'items': [{'id': str(page)}], 'totalItems': 2, 'totalPages': 2}
        with patch.object(server, 'pb_call', side_effect=pb):
            self.assertEqual([r['id'] for r in server.pending_accounts('admin-one', '192.0.2.10')], ['1', '2'])

    def test_approve_and_decline_use_caller_token(self):
        for action, method in (('approve', 'PATCH'), ('decline', 'DELETE')):
            with self.subTest(action=action):
                status, data, _ = self.request('/api/empire/approvals/pending00000001', token='admin-one',
                                              method='POST', body={action: True})
                self.assertEqual(status, 200)
                self.assertEqual(data, {'ok': True})
                self.assertEqual(self.calls[-1][2:], ('admin-one', '192.0.2.10', method))
                if action == 'approve':
                    self.assertEqual(self.calls[-1][1], {'approved': True, 'services': ['empire']})

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


WEB = Path(__file__).resolve().parent.parent / 'web'
# Resources a page loads (not links it offers): <link href>, <script src>, <img src>, CSS url().
RESOURCE = re.compile(r'<(?:link|script|img|iframe|source|video|audio)\b[^>]*?\b(?:href|src)="([^"]*)"|url\(\s*["\']?([^"\')]+)')


class LegalPageTests(unittest.TestCase):
    """Privacy policy, imprint and contact form: open without login, in their language, nothing loaded from other
    hosts."""

    def setUp(self):
        server._cache.clear()
        self.enterContext(patch.object(server.Handler, 'log_message'))
        self.enterContext(patch.dict(os.environ, {'LEGAL_PREVIEW': ''}))
        record = {'id': 'userone00000001', 'approved': True, 'services': ['empire']}
        self.enterContext(patch.object(server, 'pb_call', return_value=(200, {'record': record})))
        # A web root whose pages are approved (no draft markers), with the real frame and font.
        directory = self.enterContext(tempfile.TemporaryDirectory(dir=Path(__file__).parent))
        self.root = Path(directory)
        (self.root / 'legal').mkdir()
        shutil.copy(WEB / 'legal' / 'page.html', self.root / 'legal')
        shutil.copy(WEB / 'legal' / 'contact.js', self.root / 'legal')
        shutil.copytree(WEB / 'fonts', self.root / 'fonts')
        for entry in legal.PAGES.values():
            (self.root / 'legal' / entry.file).write_text(f'<h1>{entry.title}</h1><p>Approved text.</p>', encoding='utf-8')
        self.enterContext(patch.object(server, 'WEB_ROOT', str(self.root)))

    def test_every_page_is_open_in_its_language_with_a_link_to_the_other(self):
        for path, entry in legal.PAGES.items():
            with self.subTest(path=path):
                status, body, headers = send(path)
                self.assertEqual(status, 200)
                self.assertEqual(headers['Content-Language'], entry.language)
                self.assertTrue(headers['Content-Type'].startswith('text/html'))
                page = body.decode()
                self.assertIn(f'<html lang="{entry.language}"', page)
                self.assertIn(f'<title>{entry.title} · Ares Empire</title>', page)
                self.assertIn(f'<h1>{entry.title}</h1>', page)
                label = {'de': 'English', 'en': 'Deutsch'}[entry.language]
                self.assertRegex(page, rf'<a class="lang" href="{entry.other}"[^>]*>{label}</a>')
                self.assertIn(f'<a href="{path}" aria-current="page">', page)
                self.assertNotIn('$', page)  # every slot of the frame was filled

    def test_pages_come_in_pairs(self):
        for path, entry in legal.PAGES.items():
            pair = legal.PAGES[entry.other]
            self.assertEqual(pair.other, path)
            self.assertNotEqual(pair.language, entry.language)
        self.assertEqual(set(legal.PAGES), {'/datenschutz', '/privacy', '/impressum', '/imprint', '/kontakt', '/contact'})

    def test_logged_in_visitors_and_head_requests(self):
        status, body, _ = send('/impressum', headers={'Cookie': server.COOKIE_NAME + '=user-one'})
        self.assertEqual(status, 200)  # not redirected to the hub, unlike /login
        self.assertIn(b'Impressum', body)
        status, body, headers = send('/privacy', method='HEAD')
        self.assertEqual((status, body), (200, b''))
        self.assertGreater(int(headers['Content-Length']), 0)
        self.assertEqual(headers['Content-Language'], 'en')

    def test_font_and_its_licence_are_open(self):
        status, body, headers = send('/fonts/SpaceGrotesk-Variable.ttf')
        self.assertEqual(status, 200)
        self.assertEqual({k.lower(): v for k, v in headers.items()}['content-type'], 'font/ttf')
        self.assertEqual(body, (WEB / 'fonts' / 'SpaceGrotesk-Variable.ttf').read_bytes())
        status, body, _ = send('/fonts/OFL-SpaceGrotesk.txt')
        self.assertEqual(status, 200)
        self.assertIn(b'SIL Open Font License', body)

    def test_everything_else_stays_behind_the_login(self):
        for path in ('/legal/privacy.html', '/legal/page.html', '/legal/', '/fonts/', '/fonts/../index.html',
                     '/privacy/', '/privacy.html', '/Privacy', '/fonts/SpaceGrotesk-Variable.ttf/',
                     '/legal/contact.js', '/legal/kontakt.html', '/kontakt/', '/contact.html'):
            with self.subTest(path=path):
                status, _, headers = send(path)
                self.assertEqual(status, 303)
                self.assertEqual(headers['Location'], '/login')

    def test_drafts_are_not_served_unless_previewing(self):
        for marker in legal.DRAFT_MARKERS:
            with self.subTest(marker=marker):
                (self.root / 'legal' / 'imprint.html').write_text(f'<h1>Imprint</h1><p>{marker}</p>', encoding='utf-8')
                self.assertEqual(send('/imprint')[0], 404)
                self.assertEqual(send('/impressum')[0], 200)  # each page is published on its own
                with patch.dict(os.environ, {'LEGAL_PREVIEW': '1'}):
                    self.assertEqual(send('/imprint')[0], 200)
        (self.root / 'legal' / 'page.html').unlink()
        self.assertEqual(send('/privacy')[0], 404)

    def test_the_real_pages_load_nothing_from_other_hosts(self):
        with patch.object(server, 'WEB_ROOT', str(WEB)), patch.dict(os.environ, {'LEGAL_PREVIEW': '1'}):
            for path in legal.PAGES:
                with self.subTest(path=path):
                    status, body, _ = send(path)
                    self.assertEqual(status, 200)
                    resources = [a or b for a, b in RESOURCE.findall(body.decode())]
                    self.assertIn('/fonts/SpaceGrotesk-Variable.ttf', resources)
                    for url in resources:
                        self.assertTrue(url.startswith('/') and not url.startswith('//'), url)

    def test_the_real_pages_name_the_controller_and_the_authority(self):
        with patch.object(server, 'WEB_ROOT', str(WEB)), patch.dict(os.environ, {'LEGAL_PREVIEW': '1'}):
            for path in ('/datenschutz', '/privacy', '/impressum', '/imprint'):
                page = send(path)[1].decode()
                with self.subTest(path=path):
                    self.assertIn('Patrik Breeck', page)
                    self.assertIn('REDACTED-EMAIL', page)
                    self.assertNotIn('[ADDRESS]', page)
                    self.assertIn('85748 Garching', page)
            for path in ('/datenschutz', '/privacy'):
                self.assertIn('Promenade 18, 91522 Ansbach', send(path)[1].decode().replace('\n', ' '))

    def test_the_contact_form_is_served_only_while_the_privacy_policy_is(self):
        self.assertEqual((send('/kontakt')[0], send('/contact')[0]), (200, 200))
        (self.root / 'legal' / 'privacy.html').write_text('<h1>Privacy policy</h1><p>[ADDRESS]</p>', encoding='utf-8')
        self.assertEqual(send('/privacy')[0], 404)
        self.assertEqual(send('/contact')[0], 404)  # it collects data, so never without its policy
        self.assertEqual(send('/kontakt')[0], 200)  # the German policy is published
        with patch.dict(os.environ, {'LEGAL_PREVIEW': '1'}):
            self.assertEqual(send('/contact')[0], 200)
        (self.root / 'legal' / 'contact.js').unlink()
        self.assertEqual(send('/kontakt')[0], 404)  # a form without its script would post raw JSON pages

    def test_every_footer_links_the_contact_form_in_its_language(self):
        for path, entry in legal.PAGES.items():
            with self.subTest(path=path):
                page = send(path)[1].decode()
                contact = '/kontakt' if entry.language == 'de' else '/contact'
                self.assertRegex(page, rf'<nav>.*<a href="{contact}"')

    def test_the_real_contact_pages_hold_the_form(self):
        with patch.object(server, 'WEB_ROOT', str(WEB)), patch.dict(os.environ, {'LEGAL_PREVIEW': '1'}):
            for path, privacy in (('/kontakt', '/datenschutz'), ('/contact', '/privacy')):
                page = send(path)[1].decode()
                with self.subTest(path=path):
                    self.assertIn('action="https://auth.ares-empire.de/api/collections/contact/records"', page)
                    self.assertRegex(page, r'<input id="contact-name" name="name" type="text"[^>]*maxlength="100"')
                    self.assertRegex(page, r'<input id="contact-email" name="email" type="email"[^>]*required')
                    self.assertRegex(page, r'<textarea id="contact-message" name="message"[^>]*maxlength="5000" required')
                    # the honeypot: hidden from people and screen readers, out of the tab order
                    self.assertRegex(page, r'<div class="trap" aria-hidden="true">\s*<label[^>]*>Website</label>\s*'
                                           r'<input id="contact-website" name="website" type="text" tabindex="-1"')
                    self.assertIn(f'<a href="{privacy}">', page)
                    self.assertEqual({'empty', 'email', 'many', 'failed'}, set(re.findall(r'data-problem="(\w+)"', page)))
                    self.assertIn('id="contact-sent"', page)
                    self.assertIn('<noscript>', page)
                    # one inline script (no src), filled into the frame, after the form
                    scripts = re.findall(r'<script\b([^>]*)>', page)
                    self.assertEqual(scripts, [''])
                    self.assertIn('document.getElementById("contact-form")', page)
                    self.assertLess(page.index('id="contact-form"'), page.index('<script>'))
        self.assertNotIn('$', (WEB / 'legal' / 'contact.js').read_text())  # the frame is a string.Template

    def test_the_real_imprint_names_the_contact_form_and_the_policy_covers_it(self):
        with patch.object(server, 'WEB_ROOT', str(WEB)), patch.dict(os.environ, {'LEGAL_PREVIEW': '1'}):
            self.assertIn('<a class="keep" href="/kontakt">www.ares-empire.de/kontakt</a>', send('/impressum')[1].decode())
            self.assertIn('<a class="keep" href="/contact">www.ares-empire.de/contact</a>', send('/imprint')[1].decode())
            for path, form in (('/datenschutz', '/kontakt'), ('/privacy', '/contact')):
                page = send(path)[1].decode()
                self.assertIn(f'<a href="{form}">', page)
                self.assertIn('IONOS', page)
                self.assertIn('Art. 6', page)
        for name in ('impressum.html', 'imprint.html'):
            self.assertNotIn('lead to confirm', (WEB / 'legal' / name).read_text())

    def test_the_real_pages_read_as_legal_documents(self):
        # Patrik (2026-10-25): neutral statements, "Sie" where the reader is addressed; never "ich"/"du" or "I"/"my".
        informal = {'de': re.compile(r'\b(?i:ich|mich|mir|mein\w*|du|dich|dir|dein\w*)\b'),
                    'en': re.compile(r'\bI\b|\b(?i:me|my|mine|myself)\b')}
        for entry in legal.PAGES.values():
            text = re.sub(r'<[^>]+>', ' ', (WEB / 'legal' / entry.file).read_text(encoding='utf-8'))
            with self.subTest(page=entry.file):
                self.assertEqual(informal[entry.language].findall(text), [])
        for name, register in (('datenschutz.html', 'Sie haben das Recht'), ('kontakt.html', 'Ihre Nachricht')):
            self.assertIn(register, (WEB / 'legal' / name).read_text(encoding='utf-8'))

    def test_login_page_links_to_privacy_and_imprint(self):
        with patch.object(server, 'WEB_ROOT', str(WEB)):
            page = send('/login')[1].decode()
        self.assertIn('<a href="/privacy">Privacy</a>', page)
        self.assertIn('<a href="/imprint">Imprint</a>', page)


if __name__ == "__main__":
    unittest.main()
