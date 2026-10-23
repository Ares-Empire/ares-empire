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
        self.pending = [{'id': 'pending00000001', 'name': 'New', 'email': 'new@example.com',
                         'created': '2026-10-24 12:00:00Z', 'approved': False, 'admin': False}]
        self.calls = []
        self.state = {
            'projects': [self.province(slug) for slug in ('aresium', 'other', 'private')],
            'ideas': [{'title': 'Expansion', 'note': 'A plan'}],
            'chronicle': [{'project': p, 'text': p, 'at': '2026-10-24'}
                          for p in ('aresium', 'other', 'private', 'unknown', 'empire')],
        }
        self.catalog = {'aresium': {'users': 'coming-soon', 'app': 'aresium://'}, 'other': {'users': 'open'}}
        self.enterContext(patch.object(server, 'pb_call', side_effect=self.pb))
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

    def test_live_failure_is_null_and_cached_per_account(self):
        self.assertIsNone(self.request()[1]['projects'][0]['live'])
        self.request()
        self.assertEqual(self.pulse.call_count, 1)
        self.request(token='user-two')  # Aresium in addable also has a live field.
        self.assertEqual(self.pulse.call_count, 2)
        request = self.pulse.call_args.args[0]
        self.assertEqual(request.full_url, 'https://aresium.de/api/pulse')
        self.assertEqual(request.get_header('Authorization'), 'Bearer user-two')
        self.assertEqual(self.pulse.call_args.kwargs, {'timeout': 2})

    def test_live_success_and_expiry(self):
        self.pulse.side_effect = lambda *a, **kw: Pulse({'line': 'Nothing imported yet'})
        self.assertEqual(self.request()[1]['projects'][0]['live'], 'Nothing imported yet')
        self.request()
        self.assertEqual(self.pulse.call_count, 1)
        with patch.object(server, 'time', return_value=server.time() + 61):
            self.request()
        self.assertEqual(self.pulse.call_count, 2)

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
        self.assertEqual(server.load_catalog(), {'aresium': {'users': 'coming-soon', 'app': 'aresium://'}})

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
