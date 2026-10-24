#!/usr/bin/env bash
# Real API-rule checks against an isolated PocketBase 0.40.6. No mail hooks or live data.
set -euo pipefail
POCKETBASE="${POCKETBASE:-$HOME/.pocketbase-test/pocketbase}"
RULES_ROOT="$(cd "$(dirname "$0")" && pwd)"
if [ "$("$POCKETBASE" --version)" != "pocketbase version 0.40.6" ]; then
  echo 'FAIL PocketBase must be version 0.40.6'
  exit 1
fi
RULES_TMP="$(mktemp -d)"
RULES_PID=''
cleanup() {
  if [ -n "$RULES_PID" ]; then kill "$RULES_PID" 2>/dev/null || true; wait "$RULES_PID" 2>/dev/null || true; fi
  rm -rf "$RULES_TMP"
}
trap cleanup EXIT
mkdir "$RULES_TMP/hooks" "$RULES_TMP/public"
# Exercise the email visibility hook, without loading the production mail hooks.
cp "$RULES_ROOT/pb_hooks/admin-visibility.pb.js" "$RULES_TMP/hooks/"
RULES_PORT="$(python3 - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    print(sock.getsockname()[1])
PY
)"
RULES_PASSWORD="Rules-$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
# A disposable bootstrap identity is needed to authorize superuser creation via API.
if ! "$POCKETBASE" superuser create bootstrap@example.com "$RULES_PASSWORD" \
  --dir "$RULES_TMP/data" --migrationsDir "$RULES_ROOT/pb_migrations" \
  --hooksDir "$RULES_TMP/hooks" >"$RULES_TMP/bootstrap.log" 2>&1; then
  echo 'FAIL initialize PocketBase'
  cat "$RULES_TMP/bootstrap.log" >&2
  exit 1
fi
"$POCKETBASE" serve --automigrate=false --http "127.0.0.1:$RULES_PORT" --dir "$RULES_TMP/data" \
  --migrationsDir "$RULES_ROOT/pb_migrations" --hooksDir "$RULES_TMP/hooks" \
  --publicDir "$RULES_TMP/public" >"$RULES_TMP/server.log" 2>&1 &
RULES_PID=$!
export RULES_PORT RULES_PASSWORD RULES_TMP
python3 - <<'PY'
import json
import os
import subprocess
import sys
import time

base = 'http://127.0.0.1:' + os.environ['RULES_PORT']
password = os.environ['RULES_PASSWORD']
failures = 0
checks = 0


def call(method, path, body=None, token=''):
    args = ['curl', '--silent', '--show-error', '--max-time', '5', '--noproxy', '*',
            '--request', method, '--write-out', '\n%{http_code}', base + path]
    if token:
        args += ['--header', 'Authorization: ' + token]
    payload = None
    if body is not None:
        args += ['--header', 'Content-Type: application/json', '--data-binary', '@-']
        payload = json.dumps(body)
    result = subprocess.run(args, input=payload, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    raw, status = result.stdout.rsplit('\n', 1)
    return int(status), json.loads(raw) if raw else {}


def check(label, ok):
    global failures, checks
    checks += 1
    print(('PASS ' if ok else 'FAIL ') + label, flush=True)
    failures += not ok


def must(method, path, body=None, token=''):
    status, data = call(method, path, body, token)
    if not 200 <= status < 300:
        raise RuntimeError(f'{method} {path}: HTTP {status}: {data}')
    return data


def login(collection, email):
    return must('POST', f'/api/collections/{collection}/auth-with-password',
                {'identity': email, 'password': password})['token']


def create(email, **extra):
    return must('POST', '/api/collections/users/records', {
        'email': email, 'password': password, 'passwordConfirm': password,
        'name': 'Rules fixture', **extra}, supertoken)


def user(record_id, token=None):
    return must('GET', '/api/collections/users/records/' + record_id, token=token or supertoken)


def refused(method, record_id, body, token):
    status, _ = call(method, '/api/collections/users/records/' + record_id, body, token)
    return status in (400, 403, 404)


try:
    for attempt in range(100):
        try:
            if call('GET', '/api/health')[0] == 200:
                break
        except RuntimeError:
            pass
        time.sleep(.05)
    else:
        raise RuntimeError('PocketBase did not start')

    bootstrap = login('_superusers', 'bootstrap@example.com')
    # Isolate SMTP too: never contact the Resend host from the real migrations.
    must('PATCH', '/api/settings', {'rateLimits': {'enabled': False},
         'smtp': {'enabled': False, 'host': '127.0.0.1',
         'port': 9, 'tls': False, 'username': '', 'password': ''}}, bootstrap)
    for collection in ('users', '_superusers'):
        must('PATCH', '/api/collections/' + collection, {'authAlert': {'enabled': False}}, bootstrap)
    superuser = must('POST', '/api/collections/_superusers/records', {
        'email': 'superuser@example.com', 'password': password, 'passwordConfirm': password}, bootstrap)
    check('superuser created via API', bool(superuser['id']))
    supertoken = login('_superusers', 'superuser@example.com')
    admin = create('admin@example.com', approved=True, verified=True, services=['empire'], admin=True)
    normal = create('user@example.com', approved=True, verified=True, services=['empire'])
    pending = create('pending@example.com')
    declined = create('decline@example.com')
    admin_token = login('users', 'admin@example.com')
    user_token = login('users', 'user@example.com')
    check('admin and normal user created via API', admin['admin'] is True and not normal['admin'])

    status, _ = call('PATCH', '/api/collections/users/records/' + normal['id'],
                     {'ring': ['aresium']}, user_token)
    check('user can set own ring', status == 200 and user(normal['id'])['ring'] == ['aresium'])
    for field, value in [('approved', False), ('services', ['empire', 'aresium']),
                         ('admin', True), ('verified', False), ('services+', 'aresium'),
                         ('services-', 'empire'), ('admin+', True), ('approved+', True)]:
        before = user(normal['id'])
        denied = refused('PATCH', normal['id'], {field: value}, user_token)
        after = user(normal['id'])
        # Unsupported BoolField modifiers are ignored by PocketBase; they must be harmless.
        check('user cannot set ' + field, (denied or field in ('admin+', 'approved+')) and all(before[k] == after[k]
              for k in ('approved', 'services', 'admin', 'verified')))
    status, _ = call('PATCH', '/api/collections/users/records/' + normal['id'],
                     {'name': 'Renamed', 'password': password, 'passwordConfirm': password,
                      'oldPassword': password}, user_token)
    check('user can still rename and change password', status == 200 and user(normal['id'])['name'] == 'Renamed')
    # A password update invalidates previous tokens.
    user_token = login('users', 'user@example.com')
    for field, value in [('admin', True), ('approved', True), ('services', ['empire'])]:
        status, _ = call('POST', '/api/collections/users/records', {
            'email': 'signup-' + field + '@example.com', 'password': password,
            'passwordConfirm': password, field: value})
        check('anonymous signup cannot set ' + field, status in (400, 403))
        status, _ = call('POST', '/api/collections/users/records', {
            'email': 'admin-create-' + field + '@example.com', 'password': password,
            'passwordConfirm': password, field: value}, admin_token)
        check('admin signup cannot set ' + field, status in (400, 403))
    status, listed = call('GET', '/api/collections/users/records?filter=approved%3Dfalse', token=admin_token)
    check('admin can list pending accounts', status == 200 and
          {r['id'] for r in listed['items']} == {pending['id'], declined['id']})
    check('admin can read pending account emails',
          {r.get('email') for r in listed['items']} == {'pending@example.com', 'decline@example.com'})
    check('admin can view another account', call('GET', '/api/collections/users/records/' + normal['id'], token=admin_token)[0] == 200)
    status, _ = call('PATCH', '/api/collections/users/records/' + pending['id'],
                     {'approved': True, 'services': ['empire']}, admin_token)
    check('admin can approve and set services', status == 200 and user(pending['id'])['approved'] is True
          and user(pending['id'])['services'] == ['empire'])
    status, _ = call('PATCH', '/api/collections/users/records/' + pending['id'],
                     {'services': ['empire', 'arestemis', 'aresus']}, admin_token)
    check('admin can give the arestemis and aresus services', status == 200 and
          sorted(user(pending['id'])['services']) == ['arestemis', 'aresus', 'empire'])
    status, _ = call('PATCH', '/api/collections/users/records/' + pending['id'], {'services': ['empire']}, admin_token)
    check('unknown services are still refused', refused('PATCH', pending['id'], {'services': ['nope']}, admin_token))
    for field, value in [('email', 'changed@example.com'), ('password', password + 'new'),
                         ('admin', True), ('name', 'Changed'), ('ring', ['aresium']),
                         ('verified', True), ('emailVisibility', True), ('avatar', ''),
                         ('admin+', True), ('ring+', ['aresium'])]:
        body = {field: value}
        if field == 'password':
            body['passwordConfirm'] = value
        before = user(pending['id'])
        denied = refused('PATCH', pending['id'], body, admin_token)
        after = user(pending['id'])
        check('admin cannot change another account ' + field,
              (denied or field in ('admin+', 'ring+')) and
              {k: v for k, v in after.items() if k != 'updated'} ==
              {k: v for k, v in before.items() if k != 'updated'})
    check('admin cannot set own admin', refused('PATCH', admin['id'], {'admin': False}, admin_token))
    check('admin cannot approve own account', refused('PATCH', admin['id'], {'approved': True}, admin_token))
    status, _ = call('DELETE', '/api/collections/users/records/' + declined['id'], token=admin_token)
    check('admin can delete unapproved account', status == 204 and
          call('GET', '/api/collections/users/records/' + declined['id'], token=supertoken)[0] == 404)
    check('admin cannot delete approved account', refused('DELETE', pending['id'], None, admin_token)
          and user(pending['id'])['approved'] is True)
    check('admin cannot delete own approved account', refused('DELETE', admin['id'], None, admin_token))
    status, listed = call('GET', '/api/collections/users/records', token=user_token)
    check('non-admin cannot list others', status == 200 and [r['id'] for r in listed['items']] == [normal['id']])
    check('non-admin cannot view others', call('GET', '/api/collections/users/records/' + pending['id'], token=user_token)[0] == 404)
    check('non-admin cannot approve others', refused('PATCH', pending['id'], {'approved': False}, user_token))
    create('verified-pending@example.com', verified=True)
    check('authRule still requires verified and approved',
          call('POST', '/api/collections/users/auth-with-password',
               {'identity': 'pending@example.com', 'password': password})[0] == 403 and
          call('POST', '/api/collections/users/auth-with-password',
               {'identity': 'verified-pending@example.com', 'password': password})[0] == 403)
    status, _ = call('DELETE', '/api/collections/users/records/' + normal['id'], token=user_token)
    check('normal user can still delete own account', status == 204)
except Exception as exc:
    check(str(exc), False)
if not failures:
    print(f'PASS all {checks} API rule checks', flush=True)
sys.exit(1 if failures else 0)
PY
# Exercise the newest migrations' down and up against the same disposable database.
kill "$RULES_PID"
wait "$RULES_PID" 2>/dev/null || true
RULES_PID=''
# 0. service_arestoteles down: arestoteles is no longer offered, the four earlier services stay.
if ! printf 'y\n' | "$POCKETBASE" migrate down 1 --dir "$RULES_TMP/data" \
  --migrationsDir "$RULES_ROOT/pb_migrations" --hooksDir "$RULES_TMP/hooks" >"$RULES_TMP/down.log" 2>&1; then
  echo 'FAIL migration down (arestoteles)'
  cat "$RULES_TMP/down.log" >&2
  exit 1
fi
python3 - <<'PY'
import json, os, sqlite3, sys
with sqlite3.connect(os.environ['RULES_TMP'] + '/data/data.db') as db:
    fields = json.loads(db.execute('SELECT fields FROM _collections WHERE name = ?', ('users',)).fetchone()[0])
services = next(field for field in fields if field['name'] == 'services')
ok = services['values'] == ['empire', 'aresium', 'arestemis', 'aresus'] and services['maxSelect'] == 4
print(('PASS' if ok else 'FAIL') + ' migration down removes arestoteles only')
sys.exit(0 if ok else 1)
PY
# 1. services_arestemis_aresus down: the services field offers only empire and aresium again.
if ! printf 'y\n' | "$POCKETBASE" migrate down 1 --dir "$RULES_TMP/data" \
  --migrationsDir "$RULES_ROOT/pb_migrations" --hooksDir "$RULES_TMP/hooks" >"$RULES_TMP/down.log" 2>&1; then
  echo 'FAIL migration down (services)'
  cat "$RULES_TMP/down.log" >&2
  exit 1
fi
python3 - <<'PY'
import json, os, sqlite3, sys
with sqlite3.connect(os.environ['RULES_TMP'] + '/data/data.db') as db:
    fields = json.loads(db.execute('SELECT fields FROM _collections WHERE name = ?', ('users',)).fetchone()[0])
services = next(field for field in fields if field['name'] == 'services')
ok = services['values'] == ['empire', 'aresium'] and services['maxSelect'] == 2 and \
    {'admin', 'ring'} <= {field['name'] for field in fields}
print(('PASS' if ok else 'FAIL') + ' migration down restores the two original services')
sys.exit(0 if ok else 1)
PY
# 2. admin_ring down.
if ! printf 'y\n' | "$POCKETBASE" migrate down 1 --dir "$RULES_TMP/data" \
  --migrationsDir "$RULES_ROOT/pb_migrations" --hooksDir "$RULES_TMP/hooks" >"$RULES_TMP/down.log" 2>&1; then
  echo 'FAIL migration down'
  cat "$RULES_TMP/down.log" >&2
  exit 1
fi
python3 - <<'PY'
import json, os, sqlite3, sys
with sqlite3.connect(os.environ['RULES_TMP'] + '/data/data.db') as db:
    row = db.execute('SELECT fields, createRule, listRule, viewRule, updateRule, deleteRule, options '
                     'FROM _collections WHERE name = ?', ('users',)).fetchone()
editable = '@request.body.approved:isset = false && @request.body.services:isset = false'
ok = (not {'admin', 'ring'} & {field['name'] for field in json.loads(row[0])}
      and row[1:6] == (editable, 'id = @request.auth.id', 'id = @request.auth.id',
                      'id = @request.auth.id && ' + editable, 'id = @request.auth.id')
      and json.loads(row[6])['authRule'] == 'verified = true && approved = true')
print(('PASS' if ok else 'FAIL') + ' migration down restores users fields and rules')
sys.exit(0 if ok else 1)
PY
if "$POCKETBASE" migrate up --dir "$RULES_TMP/data" --migrationsDir "$RULES_ROOT/pb_migrations" \
  --hooksDir "$RULES_TMP/hooks" >"$RULES_TMP/up.log" 2>&1; then
  echo 'PASS migration down and up'
else
  echo 'FAIL migration down and up'
  cat "$RULES_TMP/down.log" "$RULES_TMP/up.log" >&2
  exit 1
fi
