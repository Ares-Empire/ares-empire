#!/usr/bin/env bash
# Real API-rule checks against an isolated PocketBase 0.40.6. No live data. Every hook runs; all mail goes to a local
# SMTP sink in the temp folder (never Resend, never the system's sendmail), and the account-deletion calls and the
# notifications go to a fake service on localhost (never Arestemis or the push service).
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
FAKE_PID=''
cleanup() {
  if [ -n "$RULES_PID" ]; then kill "$RULES_PID" 2>/dev/null || true; wait "$RULES_PID" 2>/dev/null || true; fi
  if [ -n "$SINK_PID" ]; then kill "$SINK_PID" 2>/dev/null || true; wait "$SINK_PID" 2>/dev/null || true; fi
  if [ -n "$FAKE_PID" ]; then kill "$FAKE_PID" 2>/dev/null || true; wait "$FAKE_PID" 2>/dev/null || true; fi
  rm -rf "$RULES_TMP"
}
trap cleanup EXIT
mkdir "$RULES_TMP/hooks" "$RULES_TMP/public" "$RULES_TMP/mail" "$RULES_TMP/fake"
# Every hook, with its shared modules (pb_hooks/lib/).
cp -R "$RULES_ROOT/pb_hooks/." "$RULES_TMP/hooks/"
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
# A fake of the services' internal routes (deletion, and the push service's /send): every request is appended to
# $RULES_TMP/fake/calls as "METHOD /<service>/<path>", and a request with a JSON body also to $RULES_TMP/fake/bodies as
# one line {"path", "body"}; the answer is the status in $RULES_TMP/fake/status-<service> (default 204), or no answer
# at all for "close".
python3 - "$RULES_TMP/fake" >"$RULES_TMP/fake.log" 2>&1 <<'PY' &
import http.server, json, os, sys, threading
folder = sys.argv[1]
lock = threading.Lock()


class Fake(http.server.BaseHTTPRequestHandler):
    def answer(self):
        length = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(length) if length else b''
        with lock:
            with open(os.path.join(folder, 'calls'), 'a') as calls:
                calls.write(f'{self.command} {self.path}\n')
            if body:
                with open(os.path.join(folder, 'bodies'), 'a') as bodies:
                    bodies.write(json.dumps({'path': self.path, 'body': json.loads(body)}) + '\n')
        service = self.path.strip('/').split('/')[0]
        try:
            with open(os.path.join(folder, 'status-' + service)) as f:
                status = f.read().strip()
        except OSError:
            status = '204'
        if status == 'close':
            self.close_connection = True
            return
        self.send_response(int(status))
        self.send_header('Content-Length', '0')
        self.end_headers()

    do_DELETE = do_GET = do_POST = answer

    def log_message(self, *args):
        pass


with http.server.ThreadingHTTPServer(('127.0.0.1', 0), Fake) as fake:
    with open(os.path.join(folder, 'port.tmp'), 'w') as port:
        port.write(str(fake.server_address[1]))
    os.rename(os.path.join(folder, 'port.tmp'), os.path.join(folder, 'port'))
    fake.serve_forever()
PY
FAKE_PID=$!
for attempt in $(seq 100); do [ -f "$RULES_TMP/fake/port" ] && break; sleep .05; done
if [ ! -f "$RULES_TMP/fake/port" ]; then
  echo 'FAIL start the fake service'
  cat "$RULES_TMP/fake.log" >&2
  exit 1
fi
FAKE_PORT="$(cat "$RULES_TMP/fake/port")"
rm "$RULES_TMP/fake/port"
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
ARESTEMIS_INTERNAL_URL="http://127.0.0.1:$FAKE_PORT/arestemis" PUSH_INTERNAL_URL="http://127.0.0.1:$FAKE_PORT/push" \
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
import shlex
import sqlite3
import subprocess
import sys
import time
import urllib.parse

base = 'http://127.0.0.1:' + os.environ['RULES_PORT']
password = os.environ['RULES_PASSWORD']
failures = 0
checks = 0


def call(method, path, body=None, token='', headers=()):
    args = ['curl', '--silent', '--show-error', '--max-time', '5', '--noproxy', '*',
            '--request', method, '--write-out', '\n%{http_code}', base + path]
    if token:
        args += ['--header', 'Authorization: ' + token]
    for header in headers:
        args += ['--header', header]
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


CONTACT = '/api/collections/contact/records'


def contact(**extra):
    return {'name': 'Fictional Visitor', 'email': 'visitor@example.com',
            'message': 'Fictional question about the imprint.', 'language': 'en', 'website': '', **extra}


FORMATS = '/api/collections/bank_formats/records'


def layout(**extra):
    """A made-up CsvLayout as the engine's shareableLayout returns it: a fictional bank's header, no name or profile."""
    return {'version': 1, 'separator': ';',
            'header': ['Buchungstag', 'Valuta', 'Empfänger', 'Verwendungszweck', 'IBAN', 'Betrag', 'Status'],
            'dateFormat': 'DD.MM.YYYY', 'numberFormat': 'de',
            'columns': {'date': 0, 'valueDate': 1, 'counterparty': [2], 'text': [3], 'iban': 4, 'amount': 5,
                        'status': 6},
            'skipStatus': ['vorgemerkt'], **extra}


def bank_format(shared=None, **extra):
    return {'bank': 'Fictional Bank', 'layout': layout() if shared is None else shared, 'app_version': '1.0 (12)',
            'language': 'en', **extra}


def stored_size(value):
    """A layout's size as PocketBase stores it: Go's compact JSON, keys sorted, UTF-8."""
    return len(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode())


def layout_of_size(total):
    """A made-up layout of exactly `total` bytes as stored, padded with status words of "ä" (2 bytes, 1 character)."""
    words = ['vorgemerkt']
    while total - stored_size(layout(skipStatus=words)) >= 163:  # a word of 80 "ä": 160 bytes, quotes and a comma
        words.append('ä' * 80)
    missing = total - stored_size(layout(skipStatus=words))
    if missing >= 3:
        words.append('ä' * ((missing - 3) // 2) + 'x' * ((missing - 3) % 2))
    elif missing:
        words[0] += 'x' * missing
    value = layout(skipStatus=words)
    assert stored_size(value) == total
    return value


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


# The administrator's refusal to leave an app or delete himself, by Accept-Language (the hub's language rule).
ADMIN_REFUSAL = [
    ('', 'This is the administrator account; it cannot leave an app or be deleted here.'),
    ('de-DE,de;q=0.9,en;q=0.8', 'Das ist das Administratorkonto. Es kann hier keine App verlassen und nicht gelöscht werden.'),
    ('en;q=0.8,de;q=0.9', 'Das ist das Administratorkonto. Es kann hier keine App verlassen und nicht gelöscht werden.'),
    ('fr, de;q=0', 'This is the administrator account; it cannot leave an app or be deleted here.'),
]

# Patrik in these checks: a made-up superuser address (superusers at example.com get no account emails).
OWNER = 'owner@ares-empire.test'
LEAVE = '/api/empire/leave'
FAKE = os.environ['RULES_TMP'] + '/fake'


def new_mails(mark, count):
    """The mails after the first `mark`, once `count` of them arrived (fewer if they do not come)."""
    return mails(at_least=mark + count)[mark:]


def quiet(mark):
    """No mail after the first `mark` (account mails go out right after the response, so wait a moment)."""
    time.sleep(.5)
    return len(mails()) == mark


def html(message):
    return message.get_body(('html',)).get_content() if message else ''


def subjects(messages):
    return [message['Subject'] for message in messages]


def fake_status(service, status):
    with open(os.path.join(FAKE, 'status-' + service), 'w') as answer:
        answer.write(str(status))


def fake_calls():
    try:
        with open(os.path.join(FAKE, 'calls')) as calls:
            return calls.read().splitlines()
    except OSError:
        return []


def pushes():
    """The notifications the account server sent to the (fake) push service, oldest first."""
    try:
        with open(os.path.join(FAKE, 'bodies')) as bodies:
            lines = [json.loads(line) for line in bodies]
    except OSError:
        return []
    return [line['body'] for line in lines if line['path'] == '/push/send']


def new_pushes(mark, count):
    """The notifications after the first `mark`, once `count` of them arrived (fewer if they do not come)."""
    for attempt in range(60):
        sent = pushes()[mark:]
        if len(sent) >= count:
            break
        time.sleep(.05)
    return sent


def no_push(mark):
    """No notification after the first `mark` (they go out right after the response, so wait a moment)."""
    time.sleep(.5)
    return len(pushes()) == mark



def ready(account, title, de_title):
    """What an account gets when it was approved or given more apps."""
    return [{'app': 'de.ares-empire.empire', 'to': {'user': account}, 'title': title,
             'body': 'Open the Empire app to start.',
             'localized': {'de': {'title': de_title, 'body': 'Öffne die Empire-App, um loszulegen.'}},
             'url': 'empire://ring', 'thread': 'access', 'collapse_id': 'ready-' + account}]


def jobs(account):
    """The deletion jobs of a deleted account, by service."""
    query = '/api/collections/deletions/records?perPage=100&filter=' + urllib.parse.quote(f"account = '{account}'")
    return {job['service']: job for job in must('GET', query, token=supertoken)['items']}


def open_jobs():
    return must('GET', '/api/collections/deletions/records?filter=done%3Dfalse', token=supertoken)['totalItems']


def run_deletions(until):
    """Runs the deletion cron once (as admin UI → Settings → Crons does; it runs in the background) and waits until
    `until()` holds."""
    must('POST', '/api/crons/empire-deletions', token=supertoken)
    for attempt in range(100):
        if until():
            return True
        time.sleep(.05)
    return False


def gone(email):
    """A made-up approved account that deletes itself; returns its id."""
    record = create(email, approved=True, verified=True, services=['arestemis'])
    must('DELETE', '/api/collections/users/records/' + record['id'], token=login('users', email))
    return record['id']


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
    must('POST', '/api/collections/_superusers/records', {
        'email': OWNER, 'password': password, 'passwordConfirm': password}, bootstrap)
    admin = create('admin@example.com', approved=True, verified=True, services=['empire'], admin=True)
    normal = create('user@example.com', approved=True, verified=True, services=['empire'])
    pending = create('pending@example.com')
    declined = create('decline@example.com')
    admin_token = login('users', 'admin@example.com')
    user_token = login('users', 'user@example.com')
    check('admin and normal user created via API', admin['admin'] is True and not normal['admin'])

    status, _ = call('PATCH', '/api/collections/users/records/' + normal['id'],
                     {'ring': ['aresium']}, user_token)
    check('an account has no saved ring any more (its ring is its services)', status == 200 and
          'ring' not in user(normal['id']))
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
                         ('admin', True), ('name', 'Changed'),
                         ('verified', True), ('emailVisibility', True), ('avatar', ''),
                         ('admin+', True), ('language', 'de')]:
        body = {field: value}
        if field == 'password':
            body['passwordConfirm'] = value
        before = user(pending['id'])
        denied = refused('PATCH', pending['id'], body, admin_token)
        after = user(pending['id'])
        check('admin cannot change another account ' + field,
              (denied or field == 'admin+') and
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
    # ...and is told why, in the request's language (a rule alone would only answer PocketBase's generic 404).
    for header, sentence in ADMIN_REFUSAL:
        status, refusal = call('DELETE', '/api/collections/users/records/' + admin['id'], token=admin_token,
                               headers=['Accept-Language: ' + header])
        check(f'deleting the admin account itself is a 403 that says why ({header})',
              status == 403 and refusal.get('message') == sentence)
    status, refusal = call('DELETE', '/api/collections/_pb_users_auth_/records/' + admin['id'], token=admin_token)
    check('also when the collection is named by its id', status == 403 and refusal.get('message') == ADMIN_REFUSAL[0][1])
    check('the admin account is still there', user(admin['id'])['admin'] is True)
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

    # One Ares account from every app (docs/ACCOUNTS.md → Accounts in every app): a sign-up asks for an app, in a
    # language; approval grants what was asked; approved accounts ask for more; an account leaves one app.
    mark = len(mails())
    push_mark = len(pushes())
    status, signed = call('POST', '/api/collections/users/records', {
        'email': 'app-signup@example.com', 'password': password, 'passwordConfirm': password,
        'name': 'Fictional Person', 'requested': ['arestemis'], 'language': 'de'})
    check('anyone can sign up asking for an app, in a language', status == 200 and
          signed.get('requested') == ['arestemis'] and signed.get('language') == 'de' and
          signed.get('approved') is False and signed.get('services') == [])
    new = new_mails(mark, 1)
    check('a sign-up is mailed to Patrik with the apps it asked for and its language', len(new) == 1 and
          new[0]['To'] == OWNER and subjects(new) == ['New Ares account: app-signup@example.com asks for Arestemis']
          and 'Language: German' in html(new[0]) and 'recordId=' + signed.get('id', '?') in html(new[0]))
    check('a sign-up is not pushed (Patrik gets the email; 2026-10-26)', no_push(push_mark))
    push_mark = len(pushes())
    for label, body in [('its record id', {'id': 'chosenaccount01'}), ('an unknown app', {'requested': ['nope']}),
                        ('an unknown language', {'language': 'fr'})]:
        status, _ = call('POST', '/api/collections/users/records', {
            'email': 'signup-' + label.replace(' ', '-') + '@example.com', 'password': password,
            'passwordConfirm': password, **body})
        check('a sign-up cannot choose ' + label, status in (400, 403))
    check('a refused sign-up is not pushed', no_push(push_mark))
    mark = len(mails())
    by_hand = create('admin-ui@example.com', requested=['empire', 'aresium'], language='en')
    check('an account made in the admin UI is not mailed to Patrik', quiet(mark))
    check('... nor pushed', no_push(push_mark))
    mark = len(mails())
    status, website = call('POST', '/api/collections/users/records', {
        'email': 'website@example.com', 'password': password, 'passwordConfirm': password, 'requested': ['empire'],
        'language': 'en'})
    check('a sign-up on the website is not pushed either', status == 200 and no_push(push_mark))
    new_mails(mark, 1)
    mark = len(mails())
    push_mark = len(pushes())

    status, _ = call('PATCH', '/api/collections/users/records/' + signed['id'],
                     {'approved': True, 'services+': ['arestemis']}, admin_token)
    after = user(signed['id'])
    check("the hub's approval grants what was requested", status == 200 and after['approved'] is True and
          after['services'] == ['arestemis'] and after['requested'] == [])
    new = new_mails(mark, 1)
    check('the approved account is mailed in its language', len(new) == 1 and
          new[0]['To'] == 'app-signup@example.com' and subjects(new) == ['Dein Ares-Konto ist bereit'] and
          'Du kannst jetzt nutzen: <b>Arestemis</b>' in html(new[0]) and 'www.ares-empire.de' not in html(new[0]))
    check('the approved account gets a notification, and nobody else', new_pushes(push_mark, 1) == ready(
          signed['id'], 'Arestemis is ready', 'Arestemis ist bereit') and no_push(push_mark + 1))
    mark = len(mails())
    push_mark = len(pushes())
    must('PATCH', '/api/collections/users/records/' + by_hand['id'], {'approved': True}, supertoken)
    after = user(by_hand['id'])
    check('switching approved on in the admin UI grants what was requested',
          after['services'] == ['empire', 'aresium'] and after['requested'] == [])
    new = new_mails(mark, 1)
    check('the approved account is mailed in English, with the hub address when it may use the hub', len(new) == 1 and
          new[0]['To'] == 'admin-ui@example.com' and subjects(new) == ['Your Ares account is ready'] and
          'You can now use: <b>Ares Empire, Aresium</b>' in html(new[0]) and
          'https://www.ares-empire.de/login' in html(new[0]))
    check('approved in the admin UI: the notification names every app it has now', new_pushes(push_mark, 1) == ready(
          by_hand['id'], 'Ares Empire and Aresium are ready', 'Ares Empire und Aresium sind bereit'))

    mark = len(mails())
    push_mark = len(pushes())
    status, asked = call('PATCH', '/api/collections/users/records/' + normal['id'],
                         {'requested': ['empire', 'arestemis'], 'language': 'de'}, user_token)
    check('an account can ask for an app and choose its language; what it has is dropped', status == 200 and
          asked.get('requested') == ['arestemis'] and asked.get('language') == 'de' and
          asked.get('services') == ['empire'])
    new = new_mails(mark, 1)
    check('an access request is mailed to Patrik', len(new) == 1 and new[0]['To'] == OWNER and
          subjects(new) == ['Ares access request: user@example.com asks for Arestemis'] and
          'Has: Ares Empire' in html(new[0]) and 'Language: German' in html(new[0]))
    check('an access request is not pushed (Patrik gets the email)', no_push(push_mark))
    mark = len(mails())
    push_mark = len(pushes())
    status, _ = call('PATCH', '/api/collections/users/records/' + normal['id'],
                     {'requested+': ['arestemis'], 'name': 'Renamed again'}, user_token)
    check('asking again for the same app is not mailed again', status == 200 and quiet(mark))
    check('... nor pushed', no_push(push_mark))
    check('an account cannot ask for another account', refused(
          'PATCH', pending['id'], {'requested': ['aresium']}, user_token) and user(pending['id'])['requested'] == [])
    query = '/api/collections/users/records?' + urllib.parse.urlencode({
        'filter': 'approved = false || requested:length > 0', 'fields': 'id,email,requested,approved', 'perPage': 100})
    status, listed = call('GET', query, token=admin_token)
    found = {r['email']: r for r in listed.get('items', [])}
    check("admins list sign-ups and approved accounts' requests (the hub's approvals)", status == 200 and
          found.get('user@example.com') == {'id': normal['id'], 'email': 'user@example.com',
                                            'requested': ['arestemis'], 'approved': True} and
          found.get('verified-pending@example.com', {}).get('approved') is False and
          'pending@example.com' not in found and 'app-signup@example.com' not in found)
    mark = len(mails())
    status, _ = call('PATCH', '/api/collections/users/records/' + normal['id'],
                     {'approved': True, 'services+': ['arestemis']}, admin_token)
    after = user(normal['id'])
    check("the hub grants an approved account's request", status == 200 and
          after['services'] == ['empire', 'arestemis'] and after['requested'] == [])
    new = new_mails(mark, 1)
    check('the granted account is mailed in its language', len(new) == 1 and new[0]['To'] == 'user@example.com' and
          subjects(new) == ['Du hast jetzt Zugang zu Arestemis'] and 'jetzt auch Zugang zu <b>Arestemis</b>' in html(new[0]))
    check('the granted account gets a notification', new_pushes(push_mark, 1) == ready(
          normal['id'], 'Arestemis is ready', 'Arestemis ist bereit'))
    mark = len(mails())
    must('PATCH', '/api/collections/users/records/' + normal['id'], {'requested': ['aresium']}, user_token)
    new_mails(mark, 1)
    mark = len(mails())
    push_mark = len(pushes())
    status, _ = call('PATCH', '/api/collections/users/records/' + normal['id'], {'requested-': ['aresium']}, admin_token)
    after = user(normal['id'])
    check("the hub's decline clears an approved account's request and keeps the account", status == 200 and
          after['requested'] == [] and after['approved'] is True and after['services'] == ['empire', 'arestemis'] and
          quiet(mark) and no_push(push_mark))
    must('PATCH', '/api/collections/users/records/' + normal['id'], {'requested': ['aresus']}, user_token)
    new_mails(mark, 1)
    mark = len(mails())
    must('PATCH', '/api/collections/users/records/' + normal['id'],
         {'services': ['empire', 'arestemis', 'aresus']}, supertoken)
    check('adding a requested app to services in the admin UI grants it',
          user(normal['id'])['requested'] == [] and subjects(new_mails(mark, 1)) == ['Du hast jetzt Zugang zu Aresus'])

    mark = len(mails())
    must('PATCH', '/api/collections/users/records/' + normal['id'], {'requested': ['aresium']}, user_token)
    new_mails(mark, 1)
    check('leaving needs a login', call('POST', LEAVE, {'service': 'arestemis'})[0] == 401)
    check('a superuser cannot leave', call('POST', LEAVE, {'service': 'arestemis'}, supertoken)[0] == 403)
    before = user(admin['id'])
    for header, sentence in ADMIN_REFUSAL:
        status, refusal = call('POST', LEAVE, {'service': 'empire'}, admin_token, headers=['Accept-Language: ' + header])
        check(f'the admin cannot leave an app: a 403 that says why ({header})',
              status == 403 and refusal.get('message') == sentence)
    after = user(admin['id'])
    check('the admin keeps its services and requests', (after['services'], after['requested']) ==
          (before['services'], before['requested']))
    status, refusal = call('POST', LEAVE, {'service': 'nope'}, user_token, headers=['Accept-Language: de'])
    check('an unknown service is refused in the request language', status == 400 and
          refusal.get('message') == 'Unbekannter Dienst.')
    for label, body in [('an unknown service', {'service': 'nope'}), ('no service', {}),
                        ('a service that is not text', {'service': 1}), ('a list', {'service': ['arestemis']})]:
        check('leaving ' + label + ' is refused (400)', call('POST', LEAVE, body, user_token)[0] == 400)
    mark = len(mails())
    status, left = call('POST', LEAVE, {'service': 'arestemis'}, 'Bearer ' + user_token)
    check('leaving an app removes its access and answers services and requested', status == 200 and
          left == {'services': ['empire', 'aresus'], 'requested': ['aresium']} and
          user(normal['id'])['services'] == ['empire', 'aresus'])
    status, left = call('POST', LEAVE, {'service': 'aresium'}, user_token)
    check('leaving an app drops an open request for it', status == 200 and
          left == {'services': ['empire', 'aresus'], 'requested': []} and user(normal['id'])['requested'] == [])
    status, again = call('POST', LEAVE, {'service': 'aresium'}, user_token)
    check('leaving an app it does not have changes nothing', status == 200 and again == left)
    check('leaving is not mailed', quiet(mark))

    # Notifications: only "your apps are ready", to the account itself (Patrik gets sign-ups and requests by email,
    # 2026-10-26); a push service that refuses or does not answer never fails the request.
    asking = create('asking@example.com', approved=True, verified=True, services=['empire'], name='')
    asking_token = login('users', 'asking@example.com')
    push_mark = len(pushes())
    must('PATCH', '/api/collections/users/records/' + asking['id'], {'requested': ['arestemis', 'aresus']}, asking_token)
    must('PATCH', '/api/collections/users/records/' + asking['id'], {'requested+': ['aresium']}, asking_token)
    check('access requests are not pushed', no_push(push_mark))
    for answer in (503, 'close'):
        fake_status('push', answer)
        status, _ = call('PATCH', '/api/collections/users/records/' + asking['id'], {'services+': ['arestoteles']},
                         admin_token)
        fake_status('push', 204)
        check(f'a push service that answers {answer} does not fail the approval', status == 200 and
              'arestoteles' in user(asking['id'])['services'])
        must('PATCH', '/api/collections/users/records/' + asking['id'], {'services-': ['arestoteles']}, admin_token)
    check('a failed push is logged', logged('push failed'))
    push_mark = len(pushes())
    must('PATCH', '/api/collections/users/records/' + asking['id'],
         {'approved': True, 'services+': ['arestemis', 'aresus', 'aresium']}, admin_token)
    check('granting three apps at once: one notification naming them', new_pushes(push_mark, 1) == ready(
          asking['id'], 'Arestemis, Aresus and Aresium are ready', 'Arestemis, Aresus und Aresium sind bereit'))
    sent = pushes()
    check('every notification tells an account only that its own apps are ready', sent and all(
          message['thread'] == 'access' and message['collapse_id'] == 'ready-' + message['to']['user']
          for message in sent))
    check('every notification is for the Empire app, in English and German', all(
          message['app'] == 'de.ares-empire.empire' and set(message['localized']) == {'de'} for message in sent))

    # PocketBase's own emails, in English and German in one message.
    mark = len(mails())
    must('POST', '/api/collections/users/request-verification', {'email': 'app-signup@example.com'})
    new = new_mails(mark, 1)
    check('the verification email is in English and German', len(new) == 1 and
          subjects(new) == ['Confirm your Ares account · Bestätige dein Ares-Konto'] and all(part in html(new[0]) for part in (
              'Confirm email address', 'E-Mail-Adresse bestätigen', '/_/#/auth/confirm-verification/')))
    mark = len(mails())
    must('POST', '/api/collections/users/request-password-reset', {'email': 'user@example.com'})
    new = new_mails(mark, 1)
    check('the password reset email is in English and German', len(new) == 1 and
          subjects(new) == ['Reset your Ares password · Setze dein Ares-Passwort zurück'] and all(part in html(new[0]) for part in (
              'Choose a new password', 'Neues Passwort wählen', '/_/#/auth/confirm-password-reset/')))

    # Contact & support (feedback): sent by the account itself, mailed to Patrik, read only by superusers.
    mark = len(mails())
    status, sent = call('POST', FEEDBACK, feedback(normal['id']), user_token)
    check('user can send own feedback', status == 200 and sent.get('user') == normal['id'])
    kept = new_mails(mark, 1)
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
          subjects(new_mails(mark, 2))[-1:] == ['[Arestoteles] Idea: ' + ' '.join(['Fictional'] * 6) + '…'])
    check("the apps' request form (Authorization: Bearer <token>) is taken", call(
          'POST', FEEDBACK, feedback(normal['id'], app='empire', kind='question'), 'Bearer ' + user_token)[0] == 200)
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

    # The website's contact form (contact): open to everyone, mailed to Patrik, read only by superusers.
    before = len(mails())
    status, written = call('POST', CONTACT, contact())
    check('anyone can send the contact form, without a login', status == 200 and written.get('email') == 'visitor@example.com')
    kept = mails(at_least=before + 1)
    mail = kept[-1] if len(kept) > before else None
    check('a contact message is mailed to Patrik, Reply-To the given email', mail is not None and
          mail['To'] == 'REDACTED-EMAIL' and mail['Reply-To'] == 'visitor@example.com' and
          mail['From'] == 'Ares Empire <noreply@ares-empire.de>' and
          mail['Subject'] == '[Website] Contact: Fictional question about the imprint.')
    text = mail.get_body(('plain',)).get_content() if mail else ''
    check('the contact mail names the name, email, language and the message', all(part in text for part in (
          'Name:     Fictional Visitor', 'Email:    visitor@example.com', 'Language: en',
          'Fictional question about the imprint.')))
    before = len(mails())
    status, _ = call('POST', CONTACT, contact(name='', language='de', message='Eine erfundene Frage ' * 5))
    german = mails(at_least=before + 1)[-1]
    check('a German message without a name: subject "Kontakt", cut on a word; the name is "–"', status == 200 and
          german['Subject'] == '[Website] Kontakt: ' + ' '.join(['Eine erfundene Frage'] * 2) + ' Eine erfundene…'
          and 'Name:     –' in german.get_body(('plain',)).get_content())
    before = len(mails())
    status, _ = call('POST', CONTACT, contact(message='Can I import two banks?\n\n— Aresium 1.0 (12) · iOS 27.0 · iPhone · Question'))
    app_mail = mails(at_least=before + 1)[-1]
    check('a message from Aresium without a login (its footer) is named so in the subject and the text', status == 200 and
          app_mail['Subject'] == '[Aresium] Contact: Can I import two banks?'
          and "A message from Aresium's Contact & support, sent without a login" in app_mail.get_body(('plain',)).get_content())
    check('a logged-in visitor can send it too', call('POST', CONTACT, contact(), user_token)[0] == 200)
    before = len(mails())
    check('the honeypot filled in is refused, and nothing is mailed',
          call('POST', CONTACT, contact(website='https://spam.example'))[0] == 400 and len(mails()) == before)
    for label, body in [('an empty message', {'message': ''}), ('a message of blanks', {'message': ' \n\t '}),
                        ('a message over 5000', {'message': 'x' * 5001}), ('no email', {'email': ''}),
                        ('an invalid email', {'email': 'not-an-email'}), ('a name over 100', {'name': 'n' * 101}),
                        ('an unknown language', {'language': 'fr'})]:
        check('contact with ' + label + ' is refused', call('POST', CONTACT, contact(**body))[0] == 400)
    check('contact of 5000 characters is taken', call('POST', CONTACT, contact(message='x' * 5000))[0] == 200)
    for who, token in [('a visitor', ''), ('a user', user_token), ('an admin', admin_token)]:
        status, listed = call('GET', CONTACT, token=token)
        check(who + ' cannot list contact messages', status == 403 or (status == 200 and listed['items'] == []))
        check(who + ' cannot view a contact message',
              call('GET', CONTACT + '/' + written['id'], token=token)[0] in (403, 404))
        check(who + ' cannot change or delete a contact message',
              call('PATCH', CONTACT + '/' + written['id'], {'message': 'Changed'}, token)[0] in (400, 403, 404)
              and call('DELETE', CONTACT + '/' + written['id'], token=token)[0] in (403, 404))
    check('superuser can view a contact message, unchanged',
          must('GET', CONTACT + '/' + written['id'], token=supertoken)['message'] == written['message'])
    # The mail fails (nothing listens on port 9): the message is kept and the failure logged.
    must('PATCH', '/api/settings', {'smtp': {**SMTP_SINK, 'port': 9}}, supertoken)
    before = len(mails())
    status, unsent = call('POST', CONTACT, contact())
    must('PATCH', '/api/settings', {'smtp': SMTP_SINK}, supertoken)
    check('a failed contact email keeps the message', status == 200 and len(mails()) == before and
          call('GET', CONTACT + '/' + unsent['id'], token=supertoken)[0] == 200)
    check('a failed contact email is logged', logged('contact email failed'))
    rules = must('GET', '/api/settings', token=supertoken)['rateLimits']['rules']
    check('contact rate limit is 5 per hour',
          {'label': 'contact:create', 'audience': '', 'duration': 3600, 'maxRequests': 5} in rules)
    # Caddy puts the visitor's address last in X-Forwarded-For; the limit counts per address.
    visitor, other = ['X-Forwarded-For: 198.51.100.7'], ['X-Forwarded-For: 198.51.100.8']
    must('PATCH', '/api/settings', {'rateLimits': {'enabled': True}}, supertoken)
    statuses = [call('POST', CONTACT, contact(message=f'Fictional message {n}'), headers=visitor)[0] for n in range(6)]
    another = call('POST', CONTACT, contact(), headers=other)[0]
    must('PATCH', '/api/settings', {'rateLimits': {'enabled': False}}, supertoken)
    check('the 6th contact message from one address within the hour is refused (429)', statuses == [200] * 5 + [429])
    check('another address can still write', another == 200)

    # Bank formats shared from Aresium (bank_formats): open to everyone, checked again on the server (nothing that
    # looks like personal data), mailed to Patrik with the command that adds the bank, read only by superusers.
    before = len(mails())
    status, shared = call('POST', FORMATS, bank_format())
    check('anyone can share a bank format, without a login', status == 200 and shared.get('bank') == 'Fictional Bank'
          and shared.get('layout') == layout() and shared.get('language') == 'en')
    kept = mails(at_least=before + 1)
    mail = kept[-1] if len(kept) > before else None
    check('a shared format is mailed to Patrik, without a Reply-To', mail is not None and
          mail['To'] == 'REDACTED-EMAIL' and mail['Reply-To'] is None and
          mail['From'] == 'Ares Empire <noreply@ares-empire.de>' and
          mail['Subject'] == 'Aresium: bank format for Fictional Bank')
    text = mail.get_body(('plain',)).get_content().replace('\r\n', '\n') if mail else ''
    saved = f"bank-format-{shared.get('id')}.json"
    check('the format mail names the bank, version, language, the record and the command', all(part in text for part in (
          'Bank:     Fictional Bank', 'Version:  1.0 (12)', 'Language: en', '(save it as ' + saved + ')',
          f"npx tsx scripts/add-shared-layout.ts {saved} --name 'Fictional Bank' --id fictional-bank",
          'collection=bank_formats&recordId=' + str(shared.get('id')))))
    block = text.split('):\n\n', 1)[-1].split('\n\n--', 1)[0]
    try:
        mailed = json.loads(block)
    except ValueError:
        mailed = None
    check('the mail holds the layout pretty-printed, as sent', mailed == layout() and '\n  "separator": ";",' in block)
    tricky = "Bank's \"Test\" $(id) `id`"
    before = len(mails())
    status, _ = call('POST', FORMATS, bank_format(bank=tricky, language='de'))
    text = mails(at_least=before + 1)[-1].get_body(('plain',)).get_content() if status == 200 else ''
    command = next((line for line in text.splitlines() if 'add-shared-layout.ts' in line), '')
    check('the command quotes any bank name as one shell word', status == 200 and command != '' and
          shlex.split(command)[4:] == ['--name', tricky, '--id', 'bank-s-test-id-id'])
    check('a logged-in app can share one too', call('POST', FORMATS, bank_format(), user_token)[0] == 200)
    edge = layout(separator='\t', header=[chr(65 + n % 26) * 80 for n in range(80)], columnCount=80,
                  columns={'date': 0, 'amount': 79, 'text': list(range(40, 80))}, invertSign=True,
                  labelledText={'labels': ['Kto/IBAN:', 'Buchungstext:'], 'counterparty': ['Empfänger:'],
                                'text': ['']}, currency='EUR')
    check('a format at the limits is taken (80 cells of 80 characters, column 79, a tab, labelled text)',
          call('POST', FORMATS, bank_format(edge))[0] == 200)
    check('a format of 8192 bytes is taken', call('POST', FORMATS, bank_format(layout_of_size(8192)))[0] == 200)

    # Refusals: a plain sentence in the request's language, the field and a code under data; nothing kept or mailed.
    PERSONAL_EN = ('The format holds something that looks like personal data (an IBAN, an email address, a date, an '
                   'amount or a long number), so it was not accepted.')
    PERSONAL_DE = ('Das Format enthält etwas, das wie persönliche Daten aussieht (eine IBAN, eine E-Mail-Adresse, ein '
                   'Datum, einen Betrag oder eine lange Zahl), deshalb wurde es nicht angenommen.')
    count = must('GET', FORMATS, token=supertoken)['totalItems']
    before = len(mails())
    iban = bank_format(layout(header=['Buchungstag', 'DE89 3704 0044 0532 0130 00', 'Betrag']))
    status, refusal = call('POST', FORMATS, iban)
    check('an IBAN in a header is refused (400) with a plain sentence and the code', status == 400 and
          refusal.get('message') == PERSONAL_EN and refusal.get('data', {}).get('layout', {}).get('code') == 'personal_data'
          and list(refusal['data']) == ['layout'])
    status, refusal = call('POST', FORMATS, iban, headers=['Accept-Language: de-DE,de;q=0.9,en;q=0.8'])
    check('... in German for a German app', status == 400 and refusal.get('message') == PERSONAL_DE)
    status, big = call('POST', FORMATS, bank_format(layout_of_size(8193)))
    check('a format of 8193 bytes is refused as too big (bytes, not characters)', status == 400 and
          big.get('message') == 'The format is too big to send.' and
          big.get('data', {}).get('layout', {}).get('code') == 'too_big' and
          len(json.dumps(layout_of_size(8193), sort_keys=True, separators=(',', ':'), ensure_ascii=False)) < 8192)
    status, big = call('POST', FORMATS, bank_format(layout(skipStatus=['x' * 80] * 80, keepStatus=['y' * 80] * 80)))
    check('a format of 13 KB is refused as too big', status == 400 and
          big.get('data', {}).get('layout', {}).get('code') == 'too_big')
    for label, body, field, code in [
        ('an IBAN without spaces in a header', layout(header=['Buchungstag', 'DE89370400440532013000']), 'layout',
         'personal_data'),
        ('a British IBAN in a header', layout(header=['GB29 NWBK 6016 1331 9268 19']), 'layout', 'personal_data'),
        ('an email address in a header', layout(header=['Buchungstag', 'max.muster@example.com']), 'layout',
         'personal_data'),
        ('a date in a header', layout(header=['27.10.2026', 'Betrag']), 'layout', 'personal_data'),
        ('an ISO date in a header', layout(header=['2026-10-27', 'Betrag']), 'layout', 'personal_data'),
        ('a date with the month\'s name', layout(header=['Buchung 27. Okt. 2026']), 'layout', 'personal_data'),
        ('an amount in a header', layout(header=['Buchungstag', '-12,34']), 'layout', 'personal_data'),
        ('an amount with its currency', layout(header=['Saldo 12 EUR']), 'layout', 'personal_data'),
        ('5 digits in a row in a status word', layout(skipStatus=['12345']), 'layout', 'personal_data'),
        ('a card number in groups in a label', layout(labelledText={'labels': ['Karte 4111 1111 1111 1111:'],
                                                                     'counterparty': [], 'text': []}),
         'layout', 'personal_data'),
        ('personal data in a field the server does not know', layout(note='Kunde 1234567'), 'layout',
         'personal_data'),
        ('the name the person gave the layout', layout(name='Konto von Max'), 'layout', 'name'),
        ('a profile', layout(profile='sparkasse-camt'), 'layout', 'name'),
        ('version 2', layout(version=2), 'layout', 'version'),
        ('no version', {k: v for k, v in layout().items() if k != 'version'}, 'layout', 'version'),
        ('a dot as separator', layout(separator='.'), 'layout', 'separator'),
        ('a header that is not a list', layout(header='Buchungstag;Betrag'), 'layout', 'header'),
        ('81 header cells', layout(header=['Spalte'] * 81), 'layout', 'header'),
        ('a header cell of 81 characters', layout(header=['x' * 81]), 'layout', 'header'),
        ('a header cell that is a number', layout(header=['Buchungstag', 7]), 'layout', 'header'),
        ('a column named by its text', layout(columns={'date': 'Buchungstag'}), 'layout', 'columns'),
        ('a column number below 0', layout(columns={'date': -1}), 'layout', 'columns'),
        ('a column number of 80', layout(columns={'date': 80}), 'layout', 'columns'),
        ('a column number with a fraction', layout(columns={'date': 0.5}), 'layout', 'columns'),
        ('a list of column lists', layout(columns={'text': [[1, 2]]}), 'layout', 'columns'),
        ('no columns', layout(columns=None), 'layout', 'columns'),
        ('a large number in another field', layout(columnCount=12345), 'layout', 'shape'),
        ('a text of 81 characters in another field', layout(skipStatus=['x' * 81]), 'layout', 'shape'),
        ('a list of 81 status words', layout(skipStatus=['offen'] * 81), 'layout', 'shape'),
        ('a field name with digits', layout(field1='x'), 'layout', 'shape'),
        ('lists nested too deep', layout(labelledText={'labels': [['Kto:']], 'counterparty': [], 'text': []}),
         'layout', 'shape'),
        ('a list instead of a layout', [layout()], 'layout', 'not_object'),
        ('a text instead of a layout', 'Buchungstag;Betrag', 'layout', 'not_object'),
    ]:
        status, refusal = call('POST', FORMATS, bank_format(body))
        check('a format with ' + label + ' is refused (' + code + ')', status == 400 and
              refusal.get('data', {}).get(field, {}).get('code') == code)
    for label, body, field, code in [
        ('an IBAN as the bank\'s name', bank_format(bank='DE89 3704 0044 0532 0130 00'), 'bank', 'personal_data'),
        ('an email address as the bank\'s name', bank_format(bank='Bank max@example.com'), 'bank', 'personal_data'),
        ('no layout', {'bank': 'Fictional Bank', 'app_version': '1.0 (12)', 'language': 'en'}, 'layout',
         'not_object'),
    ]:
        status, refusal = call('POST', FORMATS, body)
        check('a format with ' + label + ' is refused (' + code + ')', status == 400 and
              refusal.get('data', {}).get(field, {}).get('code') == code)
    for label, body, field in [('no bank', bank_format(bank=''), 'bank'), ('a blank bank', bank_format(bank='   '), 'bank'),
                               ('a bank of 101 characters', bank_format(bank='B' * 101), 'bank'),
                               ('a bank on two lines', bank_format(bank='Fictional\nBank'), 'bank'),
                               ('an unknown language', bank_format(language='fr'), 'language'),
                               ('an app version with other characters', bank_format(app_version='1.0 me@x.de'),
                                'app_version'),
                               ('an app version over 40', bank_format(app_version='1' * 41), 'app_version')]:
        status, refusal = call('POST', FORMATS, body)
        check('a format with ' + label + ' is refused', status == 400 and field in refusal.get('data', {}))
    check('a refused format is neither kept nor mailed', quiet(before) and
          must('GET', FORMATS, token=supertoken)['totalItems'] == count)
    for who, token in [('a visitor', ''), ('a user', user_token), ('an admin', admin_token)]:
        status, listed = call('GET', FORMATS, token=token)
        check(who + ' cannot list bank formats', status == 403 or (status == 200 and listed['items'] == []))
        check(who + ' cannot view a bank format', call('GET', FORMATS + '/' + shared['id'], token=token)[0] in (403, 404))
        check(who + ' cannot change or delete a bank format',
              call('PATCH', FORMATS + '/' + shared['id'], {'bank': 'Changed'}, token)[0] in (400, 403, 404)
              and call('DELETE', FORMATS + '/' + shared['id'], token=token)[0] in (403, 404))
    check('superuser can view a bank format, unchanged',
          must('GET', FORMATS + '/' + shared['id'], token=supertoken)['layout'] == layout())
    # The mail fails (nothing listens on port 9): the format is kept and the failure logged.
    must('PATCH', '/api/settings', {'smtp': {**SMTP_SINK, 'port': 9}}, supertoken)
    before = len(mails())
    status, unsent = call('POST', FORMATS, bank_format())
    must('PATCH', '/api/settings', {'smtp': SMTP_SINK}, supertoken)
    check('a failed format email keeps the format', status == 200 and len(mails()) == before and
          call('GET', FORMATS + '/' + unsent['id'], token=supertoken)[0] == 200)
    check('a failed format email is logged', logged('bank format email failed'))
    rules = must('GET', '/api/settings', token=supertoken)['rateLimits']['rules']
    check('bank format rate limit is 5 per hour',
          {'label': 'bank_formats:create', 'audience': '', 'duration': 3600, 'maxRequests': 5} in rules)
    sender, other = ['X-Forwarded-For: 198.51.100.9'], ['X-Forwarded-For: 198.51.100.10']
    must('PATCH', '/api/settings', {'rateLimits': {'enabled': True}}, supertoken)
    answers = [call('POST', FORMATS, bank_format(), headers=sender) for n in range(6)]
    another = call('POST', FORMATS, bank_format(), headers=other)[0]
    must('PATCH', '/api/settings', {'rateLimits': {'enabled': False}}, supertoken)
    check('the 6th format from one address within the hour is refused (429)',
          [status for status, _ in answers] == [200] * 5 + [429] and answers[-1][1].get('status') == 429)
    check('another address can still share one', another == 200)

    # PocketBase also runs the deletion cron by itself every 5 minutes. From here to the end, the checks need a minute
    # without such a run (the deletion just below must still find its jobs open), so wait for one first if it is near.
    wait = 300 - time.time() % 300
    if wait < 60:
        time.sleep(wait + 2)
    status, _ = call('DELETE', '/api/collections/users/records/' + normal['id'], token=user_token)
    check('normal user can still delete own account', status == 204)
    query = FEEDBACK + '?filter=' + urllib.parse.quote(f"user = '{normal['id']}'")
    check("an account's feedback goes with the account", must('GET', query, token=supertoken)['totalItems'] == 0)

    # Deleting an account reaches every service: one job per service, the cron calls the fake service.
    check('the deleted account got one open job per service', {
        service: (job['done'], job['attempts']) for service, job in jobs(normal['id']).items()} ==
        {'arestemis': (False, 0), 'push': (False, 0)})
    check('an account declined by an admin gets its jobs too', set(jobs(declined['id'])) == {'arestemis', 'push'})
    check('the cron calls every open job and a 2xx closes it', run_deletions(lambda: open_jobs() == 0) and
          all(f'DELETE /{service}/internal/accounts/{account}' in fake_calls()
              for service in ('arestemis', 'push') for account in (normal['id'], declined['id'])))
    for who, token in [('an admin', admin_token), ('anyone', '')]:
        status, listed = call('GET', '/api/collections/deletions/records', token=token)
        check(who + ' cannot list deletion jobs', status == 403 or (status == 200 and listed['items'] == []))
        check(who + ' cannot create deletion jobs', call('POST', '/api/collections/deletions/records', {
            'account': 'fictional000001', 'service': 'push'}, token)[0] in (400, 403))
    first = gone('gone-one@example.com')
    fake_status('arestemis', 503)
    fake_status('push', 404)
    ran = run_deletions(lambda: jobs(first)['push']['done'] and jobs(first)['arestemis']['attempts'] == 1)
    job = jobs(first)['arestemis']
    check('a failing service keeps its job open with the error; a 404 closes it', ran and job['done'] is False and
          job['last_error'] == 'HTTP 503' and jobs(first)['push']['done'] is True)
    fake_status('arestemis', 204)
    ran = run_deletions(lambda: jobs(first)['arestemis']['done'])
    job = jobs(first)['arestemis']
    check('the next run tries it again', ran and job['attempts'] == 2 and job['last_error'] == '')
    second, third = gone('gone-two@example.com'), gone('gone-three@example.com')
    fake_status('arestemis', 'close')
    ran = run_deletions(lambda: jobs(third)['push']['done'] and jobs(second)['arestemis']['attempts'] == 1)
    check('a service that does not answer is not called again in the same run', ran and
          jobs(second)['arestemis']['last_error'] != '' and jobs(third)['arestemis']['attempts'] == 0 and
          fake_calls().count(f'DELETE /arestemis/internal/accounts/{third}') == 0)
    stuck = jobs(second)['arestemis']
    with sqlite3.connect(os.environ['RULES_TMP'] + '/data/data.db', timeout=5) as db:
        db.execute('UPDATE deletions SET created = ? WHERE id = ?', ('2026-01-01 00:00:00.000Z', stuck['id']))
    mark = len(mails())
    ran = run_deletions(lambda: jobs(second)['arestemis']['attempts'] == 2)
    new = new_mails(mark, 1)
    check('a job still failing a day after the deletion is mailed to Patrik', ran and len(new) == 1 and
          new[0]['To'] == OWNER and subjects(new) == ['Ares account deletion stuck: Arestemis'] and
          second in html(new[0]) and jobs(second)['arestemis']['reported'] is True)
    mark = len(mails())
    ran = run_deletions(lambda: jobs(second)['arestemis']['attempts'] == 3)
    check('... once', ran and quiet(mark))
    fake_status('arestemis', 204)
    check('once the service answers, every job closes', run_deletions(lambda: open_jobs() == 0))
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
migrate_down() {
  if ! printf 'y\n' | "$POCKETBASE" migrate down 1 --dir "$RULES_TMP/data" \
    --migrationsDir "$RULES_ROOT/pb_migrations" --hooksDir "$RULES_TMP/hooks" >"$RULES_TMP/down.log" 2>&1; then
    echo "FAIL migration down ($1)"
    cat "$RULES_TMP/down.log" >&2
    exit 1
  fi
}
# The rules of the users collection as the migrations write them: an account may change its own record except these
# fields; an admin may change only approved, services and requested of another account (every other field named).
cat >"$RULES_TMP/users_rules.py" <<'PY'
import json, os, sqlite3
OWN = ('@request.body.approved:isset = false && @request.body.services:isset = false && '
       '@request.body.admin:isset = false && @request.body.verified:isset = false')


def users():
    with sqlite3.connect(os.environ['RULES_TMP'] + '/data/data.db') as db:
        fields, update = db.execute('SELECT fields, updateRule FROM _collections WHERE name = ?', ('users',)).fetchone()
    return [field['name'] for field in json.loads(fields)], update


def update_rule(names, admin_may_change):
    untouchable = [name for name in names if name not in admin_may_change] + ['passwordConfirm', 'oldPassword']
    return ('(id = @request.auth.id && ' + OWN + ') || (@request.auth.admin = true && id != @request.auth.id && ' +
            ' && '.join('@request.body.' + name + ':isset = false' for name in untouchable) + ')')
PY
# bank_formats down (the newest): the collection and its rate limit are gone, the contact form stays.
migrate_down 'bank formats'
python3 - <<'PY'
import json, os, sqlite3, sys
with sqlite3.connect(os.environ['RULES_TMP'] + '/data/data.db') as db:
    collections = {row[0] for row in db.execute('SELECT name FROM _collections')}
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    settings = json.loads(db.execute("SELECT value FROM _params WHERE id = 'settings'").fetchone()[0])
labels = [rule['label'] for rule in settings['rateLimits']['rules']]
ok = ('bank_formats' not in collections | tables and 'bank_formats:create' not in labels
      and 'contact' in collections and 'contact:create' in labels)
print(('PASS' if ok else 'FAIL') + ' migration down removes the bank_formats collection and its rate limit')
sys.exit(0 if ok else 1)
PY
# 0. drop_ring down: the ring field is back (empty), and the admins' rule names it again.
migrate_down 'ring'
python3 - <<'PY'
import os, sys
sys.path.insert(0, os.environ['RULES_TMP'])
from users_rules import update_rule, users
names, update = users()
ok = 'ring' in names and update == update_rule(names, ('approved', 'services', 'requested'))
print(('PASS' if ok else 'FAIL') + ' migration down brings the ring field back and names it in the admins\' rule')
sys.exit(0 if ok else 1)
PY
# a. emails_de_en down: PocketBase's own templates again.
migrate_down 'emails'
python3 - <<'PY'
import json, os, sqlite3, sys
with sqlite3.connect(os.environ['RULES_TMP'] + '/data/data.db') as db:
    options = json.loads(db.execute('SELECT options FROM _collections WHERE name = ?', ('users',)).fetchone()[0])
ok = (options['verificationTemplate']['subject'] == 'Verify your {APP_NAME} email' and
      options['resetPasswordTemplate']['subject'] == 'Reset your {APP_NAME} password' and
      'Thank you for joining us' in options['verificationTemplate']['body'])
print(('PASS' if ok else 'FAIL') + ' migration down restores PocketBase\'s email templates')
sys.exit(0 if ok else 1)
PY
# b. deletions down: the collection is gone, the accounts stay.
migrate_down 'deletions'
python3 - <<'PY'
import os, sqlite3, sys
with sqlite3.connect(os.environ['RULES_TMP'] + '/data/data.db') as db:
    collections = {row[0] for row in db.execute('SELECT name FROM _collections')}
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
ok = 'deletions' not in collections | tables and 'users' in collections
print(('PASS' if ok else 'FAIL') + ' migration down removes the deletions collection')
sys.exit(0 if ok else 1)
PY
# c. requested_language down: the two fields go, the rules are the ones of admin_ring again.
migrate_down 'requested and language'
python3 - <<'PY'
import json, os, sqlite3, sys
with sqlite3.connect(os.environ['RULES_TMP'] + '/data/data.db') as db:
    fields, create, update = db.execute(
        'SELECT fields, createRule, updateRule FROM _collections WHERE name = ?', ('users',)).fetchone()
names = [field['name'] for field in json.loads(fields)]
own = ('@request.body.approved:isset = false && @request.body.services:isset = false && '
       '@request.body.admin:isset = false && @request.body.verified:isset = false')
untouchable = [name for name in names if name not in ('approved', 'services')] + ['passwordConfirm', 'oldPassword']
admin = ('(@request.auth.admin = true && id != @request.auth.id && ' +
         ' && '.join('@request.body.' + name + ':isset = false' for name in untouchable) + ')')
ok = not {'requested', 'language'} & set(names) and create == own and update == '(id = @request.auth.id && ' + own + ') || ' + admin
print(('PASS' if ok else 'FAIL') + ' migration down removes requested and language and restores the rules')
sys.exit(0 if ok else 1)
PY
# 0. contact down: the collection and its rate limit are gone, feedback stays.
if ! printf 'y\n' | "$POCKETBASE" migrate down 1 --dir "$RULES_TMP/data" \
  --migrationsDir "$RULES_ROOT/pb_migrations" --hooksDir "$RULES_TMP/hooks" >"$RULES_TMP/down.log" 2>&1; then
  echo 'FAIL migration down (contact)'
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
ok = ('contact' not in collections | tables and 'contact:create' not in labels
      and 'feedback' in collections and 'feedback:create' in labels)
print(('PASS' if ok else 'FAIL') + ' migration down removes the contact collection and its rate limit')
sys.exit(0 if ok else 1)
PY
# 1. feedback down: the collection and its rate limit are gone, the accounts stay.
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
# 2. service_arestoteles down: arestoteles is no longer offered, the four earlier services stay.
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
# 3. services_arestemis_aresus down: the services field offers only empire and aresium again.
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
# 4. admin_ring down.
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
    fields = json.loads(db.execute('SELECT fields FROM _collections WHERE name = ?', ('users',)).fetchone()[0])
    options = json.loads(db.execute('SELECT options FROM _collections WHERE name = ?', ('users',)).fetchone()[0])
labels = [rule['label'] for rule in settings['rateLimits']['rules']]
ok = ({'feedback', 'contact'} <= collections and labels.count('feedback:create') == 1
      and labels.count('contact:create') == 1)
print(('PASS' if ok else 'FAIL') + ' migration up adds the feedback and contact collections, one rate limit each')
again = ('deletions' in collections and {'requested', 'language'} <= {field['name'] for field in fields} and
         options['verificationTemplate']['subject'] == 'Confirm your Ares account · Bestätige dein Ares-Konto')
print(('PASS' if again else 'FAIL') + ' migration up adds requested, language, deletions and the two-language emails again')
formats = 'bank_formats' in collections and labels.count('bank_formats:create') == 1
print(('PASS' if formats else 'FAIL') + ' migration up adds the bank_formats collection and its rate limit again')
ok = ok and again and formats
sys.exit(0 if ok else 1)
PY
python3 - <<'PY'
import os, sys
sys.path.insert(0, os.environ['RULES_TMP'])
from users_rules import update_rule, users
names, update = users()
ok = 'ring' not in names and 'ring' not in update and update == update_rule(names, ('approved', 'services', 'requested'))
print(('PASS' if ok else 'FAIL') + ' migration up drops the ring field and its place in the admins\' rule again')
sys.exit(0 if ok else 1)
PY
