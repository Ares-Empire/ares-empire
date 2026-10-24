#!/usr/bin/env bash
# Real API-rule checks against an isolated PocketBase 0.40.6. No live data. Of the mail hooks only the feedback hook
# runs, and its mail goes to a local SMTP sink in the temp folder (never Resend, never the system's sendmail).
set -euo pipefail
POCKETBASE="${POCKETBASE:-$HOME/.pocketbase-test/pocketbase}"
RULES_ROOT="$(cd "$(dirname "$0")" && pwd)"
if [ "$("$POCKETBASE" --version)" != "pocketbase version 0.40.6" ]; then
  echo 'FAIL PocketBase must be version 0.40.6'
  exit 1
fi
RULES_TMP="$(mktemp -d)"
RULES_PID=''
SINK_PID=''
cleanup() {
  if [ -n "$RULES_PID" ]; then kill "$RULES_PID" 2>/dev/null || true; wait "$RULES_PID" 2>/dev/null || true; fi
  if [ -n "$SINK_PID" ]; then kill "$SINK_PID" 2>/dev/null || true; wait "$SINK_PID" 2>/dev/null || true; fi
  rm -rf "$RULES_TMP"
}
trap cleanup EXIT
mkdir "$RULES_TMP/hooks" "$RULES_TMP/public" "$RULES_TMP/mail"
# Exercise the email visibility hook and the feedback mail hook, without the sign-up mail hooks.
cp "$RULES_ROOT/pb_hooks/admin-visibility.pb.js" "$RULES_ROOT/pb_hooks/feedback.pb.js" "$RULES_TMP/hooks/"
# A local SMTP sink: accepts every message and writes it to $RULES_TMP/mail/<n>.eml (no TLS, no auth, no relaying).
python3 - "$RULES_TMP/mail" >"$RULES_TMP/sink.log" 2>&1 <<'PY' &
import itertools, os, socketserver, sys
folder = sys.argv[1]
numbers = itertools.count(1)


class Session(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(b'220 sink ESMTP\r\n')
        while line := self.rfile.readline():
            verb = line[:4].upper()
            if verb == b'DATA':
                self.wfile.write(b'354 end with a dot\r\n')
                lines = []
                while (part := self.rfile.readline()) not in (b'.\r\n', b''):
                    lines.append(part[1:] if part.startswith(b'..') else part)
                with open(os.path.join(folder, f'{next(numbers)}.eml'), 'wb') as message:
                    message.writelines(lines)
                self.wfile.write(b'250 kept\r\n')
            elif verb == b'QUIT':
                self.wfile.write(b'221 bye\r\n')
                return
            else:  # EHLO (no extensions: no STARTTLS, no AUTH), MAIL, RCPT, RSET, NOOP
                self.wfile.write(b'250 ok\r\n')


class Sink(socketserver.ThreadingTCPServer):
    daemon_threads = True


with Sink(('127.0.0.1', 0), Session) as sink:
    with open(os.path.join(folder, 'port.tmp'), 'w') as port:
        port.write(str(sink.server_address[1]))
    os.rename(os.path.join(folder, 'port.tmp'), os.path.join(folder, 'port'))
    sink.serve_forever()
PY
SINK_PID=$!
for attempt in $(seq 100); do [ -f "$RULES_TMP/mail/port" ] && break; sleep .05; done
if [ ! -f "$RULES_TMP/mail/port" ]; then
  echo 'FAIL start the SMTP sink'
  cat "$RULES_TMP/sink.log" >&2
  exit 1
fi
SINK_PORT="$(cat "$RULES_TMP/mail/port")"
rm "$RULES_TMP/mail/port"
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
export RULES_PORT RULES_PASSWORD RULES_TMP SINK_PORT
python3 - <<'PY'
import email
import email.policy
import json
import os
import subprocess
import sys
import time
import urllib.parse

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


FEEDBACK = '/api/collections/feedback/records'
SMTP_SINK = {'enabled': True, 'host': '127.0.0.1', 'port': int(os.environ['SINK_PORT']), 'tls': False,
             'username': '', 'password': ''}


def feedback(owner, **extra):
    return {'user': owner, 'app': 'arestoteles', 'kind': 'idea',
            'message': 'Fictional idea: search could also look inside the panels.',
            'app_version': '1.0 (12)', 'system': 'iOS 27.0 · iPhone', 'language': 'en', **extra}


def mails(at_least=0):
    """The messages the SMTP sink kept, oldest first (waits a moment for `at_least` of them)."""
    folder = os.environ['RULES_TMP'] + '/mail'
    for attempt in range(60):
        names = sorted(os.listdir(folder), key=lambda name: int(name.split('.')[0]))
        if len(names) >= at_least:
            break
        time.sleep(.05)
    return [email.message_from_bytes(open(os.path.join(folder, name), 'rb').read(), policy=email.policy.default)
            for name in names]


def logged(message):
    """Whether PocketBase logged `message` (its logger writes in batches, so give it a few seconds)."""
    query = '/api/logs?filter=' + urllib.parse.quote(f"message = '{message}'")
    for attempt in range(80):
        if must('GET', query, token=supertoken)['totalItems']:
            return True
        time.sleep(.1)
    return False


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
    # Isolate SMTP too: never contact the Resend host from the real migrations. Mail goes to the local sink (with
    # SMTP switched off, PocketBase would hand it to the system's sendmail instead).
    must('PATCH', '/api/settings', {'rateLimits': {'enabled': False}, 'smtp': SMTP_SINK}, bootstrap)
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

    # Contact & support (feedback): sent by the account itself, mailed to Patrik, read only by superusers.
    status, sent = call('POST', FEEDBACK, feedback(normal['id']), user_token)
    check('user can send own feedback', status == 200 and sent.get('user') == normal['id'])
    kept = mails(at_least=1)
    mail = kept[-1] if kept else None
    check('feedback is mailed to Patrik, Reply-To the account', len(kept) == 1 and
          mail['To'] == 'REDACTED-EMAIL' and mail['Reply-To'] == 'user@example.com' and
          mail['From'] == 'Ares Empire <noreply@ares-empire.de>' and
          mail['Subject'] == '[Arestoteles] Idea: Fictional idea: search could also look inside the panels.')
    text = mail.get_body(('plain',)).get_content() if mail else ''
    check('feedback mail names kind, app, version, system, language, account and the message',
          all(part in text for part in ('Kind:     Idea', 'App:      Arestoteles', 'Version:  1.0 (12)',
                                        'System:   iOS 27.0 · iPhone', 'Language: en', 'Account:  user@example.com',
                                        'Fictional idea: search could also look inside the panels.')))
    status, _ = call('POST', FEEDBACK, feedback(normal['id'], message='Fictional ' * 20), user_token)
    check('the subject cuts a long message on a word', status == 200 and
          mails(at_least=2)[-1]['Subject'] == '[Arestoteles] Idea: ' + ' '.join(['Fictional'] * 6) + '…')
    check('user cannot send feedback as another account',
          call('POST', FEEDBACK, feedback(admin['id']), user_token)[0] in (400, 403))
    check('feedback without a login is refused', call('POST', FEEDBACK, feedback(normal['id']))[0] in (400, 403))
    for label, body in [('an unknown kind', {'kind': 'complaint'}), ('an unknown app', {'app': 'nope'}),
                        ('no kind', {'kind': ''}), ('no app', {'app': ''}), ('an empty message', {'message': ''}),
                        ('a message of blanks', {'message': '  \n  '}), ('a message over 5000', {'message': 'x' * 5001}),
                        ('a version over 40', {'app_version': '1' * 41}), ('a system over 80', {'system': 's' * 81}),
                        ('an unknown language', {'language': 'fr'})]:
        check('feedback with ' + label + ' is refused',
              call('POST', FEEDBACK, feedback(normal['id'], **body), user_token)[0] == 400)
    check('feedback of 5000 characters is taken',
          call('POST', FEEDBACK, feedback(normal['id'], message='x' * 5000), user_token)[0] == 200)
    for who, token in [('user', user_token), ('admin', admin_token)]:
        status, listed = call('GET', FEEDBACK, token=token)
        check(who + ' cannot list feedback', status == 403 or (status == 200 and listed['items'] == []))
        check(who + ' cannot view feedback', call('GET', FEEDBACK + '/' + sent['id'], token=token)[0] in (403, 404))
    check('user cannot change own feedback',
          call('PATCH', FEEDBACK + '/' + sent['id'], {'message': 'Changed'}, user_token)[0] in (403, 404))
    check('user cannot delete own feedback', call('DELETE', FEEDBACK + '/' + sent['id'], token=user_token)[0] in (403, 404)
          and must('GET', FEEDBACK + '/' + sent['id'], token=supertoken)['message'] == sent['message'])
    listed = must('GET', FEEDBACK + '?perPage=100', token=supertoken)
    check('superuser can list and view feedback', sent['id'] in {r['id'] for r in listed['items']})
    revoked = create('revoked@example.com', approved=True, verified=True, services=['empire'])
    revoked_token = login('users', 'revoked@example.com')
    must('PATCH', '/api/collections/users/records/' + revoked['id'], {'approved': False}, supertoken)
    check('an account no longer approved cannot send feedback',
          call('POST', FEEDBACK, feedback(revoked['id']), revoked_token)[0] in (400, 403))
    # The mail fails (nothing listens on port 9): the feedback is kept and the failure logged.
    must('PATCH', '/api/settings', {'smtp': {**SMTP_SINK, 'port': 9}}, supertoken)
    before = len(mails())
    status, unsent = call('POST', FEEDBACK, feedback(normal['id'], kind='problem'), user_token)
    must('PATCH', '/api/settings', {'smtp': SMTP_SINK}, supertoken)
    check('a failed feedback email keeps the feedback', status == 200 and len(mails()) == before and
          call('GET', FEEDBACK + '/' + unsent['id'], token=supertoken)[0] == 200)
    check('a failed feedback email is logged', logged('feedback email failed'))
    rules = must('GET', '/api/settings', token=supertoken)['rateLimits']['rules']
    check('feedback rate limit is 10 per hour',
          {'label': 'feedback:create', 'audience': '', 'duration': 3600, 'maxRequests': 10} in rules)
    must('PATCH', '/api/settings', {'rateLimits': {'enabled': True}}, supertoken)
    statuses = [call('POST', FEEDBACK, feedback(normal['id'], message=f'Fictional message {n}'), user_token)[0]
                for n in range(11)]
    must('PATCH', '/api/settings', {'rateLimits': {'enabled': False}}, supertoken)
    check('the 11th feedback within the hour is refused (429)', statuses == [200] * 10 + [429])

    status, _ = call('DELETE', '/api/collections/users/records/' + normal['id'], token=user_token)
    check('normal user can still delete own account', status == 204)
    query = FEEDBACK + '?filter=' + urllib.parse.quote(f"user = '{normal['id']}'")
    check("an account's feedback goes with the account", must('GET', query, token=supertoken)['totalItems'] == 0)
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
# 0. feedback down: the collection and its rate limit are gone, the accounts stay.
if ! printf 'y\n' | "$POCKETBASE" migrate down 1 --dir "$RULES_TMP/data" \
  --migrationsDir "$RULES_ROOT/pb_migrations" --hooksDir "$RULES_TMP/hooks" >"$RULES_TMP/down.log" 2>&1; then
  echo 'FAIL migration down (feedback)'
  cat "$RULES_TMP/down.log" >&2
  exit 1
fi
python3 - <<'PY'
import json, os, sqlite3, sys
with sqlite3.connect(os.environ['RULES_TMP'] + '/data/data.db') as db:
    collections = {row[0] for row in db.execute('SELECT name FROM _collections')}
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    settings = json.loads(db.execute("SELECT value FROM _params WHERE id = 'settings'").fetchone()[0])
labels = [rule['label'] for rule in settings['rateLimits']['rules']]
ok = 'feedback' not in collections | tables and 'feedback:create' not in labels and 'users' in collections
print(('PASS' if ok else 'FAIL') + ' migration down removes the feedback collection and its rate limit')
sys.exit(0 if ok else 1)
PY
# 1. service_arestoteles down: arestoteles is no longer offered, the four earlier services stay.
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
# 2. services_arestemis_aresus down: the services field offers only empire and aresium again.
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
# 3. admin_ring down.
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
python3 - <<'PY'
import json, os, sqlite3, sys
with sqlite3.connect(os.environ['RULES_TMP'] + '/data/data.db') as db:
    collections = {row[0] for row in db.execute('SELECT name FROM _collections')}
    settings = json.loads(db.execute("SELECT value FROM _params WHERE id = 'settings'").fetchone()[0])
labels = [rule['label'] for rule in settings['rateLimits']['rules']]
ok = 'feedback' in collections and labels.count('feedback:create') == 1
print(('PASS' if ok else 'FAIL') + ' migration up adds the feedback collection and one rate limit again')
sys.exit(0 if ok else 1)
PY
