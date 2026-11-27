# Home-front SSH

Home-front manages the owner's SSH forwarding accounts on the server. A `listen` account can bind its listed server
loopback ports through reverse SSH. An `open` account can reach its listed server loopback ports through SSH. Each
account has its own Ed25519 key, and its sshd policy and key line both enforce its port list. SSH sessions for shells,
commands and subsystems are disabled. Agent, X11, Unix socket, and tunnel-device forwarding are disabled.

## Install by hand

Before every run, hold an admin SSH session open. After the run, **open a fresh admin SSH session from the Mac**
before closing the held one. If a fresh login fails, use the held session to inspect SSH configuration and logs.
The provider's console is the last resort. Keep real addresses, hostnames, and keys in private server files.

1. As root, create `/etc/home-front` with mode `0700`. Create the root-owned
   `/etc/home-front/admin-sources` with mode `0600`. List every admin connection source as
   `hostname IP-address`, one per line. For example:

   ```text
   admin.example.net 192.0.2.10
   console.example.net 192.0.2.11
   ```

2. Run `sudo bash deploy/install-home-front.sh` from the checkout. It installs
   `/usr/local/sbin/home-front`, creates an empty private machines file if needed, and puts the marked Include
   at the end of `/etc/ssh/sshd_config`. The only other allowed Include is Debian's
   `Include /etc/ssh/sshd_config.d/*.conf`. Use plain ASCII filenames and unquoted directive keywords. Resolve any
   reported `Match` directive or Include placement before retrying.

3. As root, declare each account in `/etc/home-front/machines` (mode `0600`). See [example machines](../home-front/machines).
   Each line contains `account kind port[,port...] [alive=secondsxcount]`. Service ports are 20001–20099 and
   SSH ports are 20101–20199. Each listen port has one owner. Open accounts may share a destination port.
   The default client keepalive is `5x3`.

4. Generate an Ed25519 key on each client. Transfer only its public half. On the server, run
   `sudo home-front add-machine tunnel-test tunnel-test.pub` or
   `sudo home-front add-machine jump-test jump-test.pub` for the corresponding declared account.

Home-front never changes root's effective sshd settings and compares them before and after reload. It validates
root's baseline for every admin source and checks each provisioned account from three sources. It saves root's
settings in `/var/lib/home-front/sshd-before/`. Home-front cannot distinguish an unrelated pending edit in another
sshd file from an intended one. A reload activates pending edits, as any sshd reload or package upgrade would.

Use literal home-relative global key paths without percent tokens and leave host-based, GSSAPI and
keyboard-interactive authentication disabled.
The dedicated accounts' home directory must remain absent. These conditions keep machine credentials unusable if a
package upgrade drops the managed Include.

## Restore after interruption

Before writing, home-front saves the previous files in a private, timestamped directory under
`/var/lib/home-front/backup/`. It retains these backups. On a caught error, it attempts to restore the files and
reports the outcome. An incomplete rollback, power loss, or uncatchable signal leaves an `in-progress` marker.
The next command prints the backup path and the commands below. Run them from the held session or the provider's
console. The restore script checks that the marker names its backup before restoring files or clearing the marker.
A marker cleanup error after a verified commit leaves the applied policy in place.

```bash
backup=$(sudo cat /var/lib/home-front/in-progress)
sudo bash "$backup/restore.sh" && \
sudo /usr/sbin/sshd -t && sudo systemctl reload ssh.service
```

After a fresh Mac login succeeds, run `sudo bash "$backup/restore.sh" --clear-marker`.

## Manage accounts

- `sudo home-front status` checks the Include and each account's policy, key and ports, and reports the last accepted
  key login from the retained SSH journal.
- `sudo home-front render` applies machine policy. Kind and ports are fixed in the Linux account's comment when
  the account is created. Use a new account name for different permissions. The installer, render, add and remove
  share the lock at `/run/home-front.lock`.
- `sudo home-front remove-machine tunnel-test` checks the account's home-front policy comment, expires it, deletes
  its key and kills processes by UID and by exact account matches in SSH authentication titles. Post-login workers
  are matched by UID. Removal keeps the passwd entry, checks that the UID is unchanged, and requires two clean
  process checks one second apart before printing `CLOSED (verified)`.
  If it prints `REVOCATION UNCONFIRMED`, follow the printed next step.
- To re-add an expired account with the same kind and ports, run `add-machine` with its public key. Expiry is
  cleared after the key and reloaded policy have been verified and the marker removal has been synced.
  For a different key on an active account, run `remove-machine` first and wait for `CLOSED (verified)`.
  Repeating the same key leaves its key file in place.

This package manages SSH. When public routes have been added, use the server-front controls to close and verify them
as part of machine removal. The SSH-only removal reports an unconfirmed outcome if it finds routes for that account.
P1b will wire `remove-machine` to the route-off operation in design section 5.2.

## Server acceptance

With a separate admin SSH session held open, put these two fixture rows in `/etc/home-front/machines`:

```text
tunnel-test listen 20097,20099,20199
jump-test open 20199
```

Run on the server as root. The acceptance client connects from IPv4 loopback, so sshd must accept loopback connections
on port 22, or pass `--port PORT`. Ports 9999, 20097, 20098, 20099 and 20199 must be free. Supply disposable keys
created on the server for this test client and pin the server's host key under the test alias. If sshd uses a different
Ed25519 host key, use the corresponding local public key file when making the pin.

```bash
fixture=$(mktemp -d)
ssh-keygen -q -t ed25519 -N '' -f "$fixture/tunnel"
ssh-keygen -q -t ed25519 -N '' -f "$fixture/jump"
awk '{print "server.example.net", $1, $2}' /etc/ssh/ssh_host_ed25519_key.pub > "$fixture/known_hosts"
bash home-front/acceptance-ssh.sh "$fixture/tunnel" "$fixture/jump" "$fixture/known_hosts"
```

Acceptance captures root settings before the first change and compares them after every reload. It checks allowed
and forbidden forwarding, including a jump reverse bind on free port 20199, two simultaneous holders, and both kinds of
revocation. It runs 10 authenticated retries against the occupied port at two-second intervals, attempts a fresh SSH
login from the same address and reads the SSH journal. A reported source penalty is a rollout stop. Keep the output
and investigate it before continuing. On success the script re-authorizes both test keys. Keep the private fixture
directory for a server-side rerun. To use a different fixture key, remove the corresponding account first.

## Local verification

`python3 -m unittest home-front/test_render.py` exercises the policy and installer with a scratch filesystem and an
injected command runner. `HOME_FRONT_ROOT` redirects managed paths, including the lock.
`HOME_FRONT_RUNNER` receives the command name followed by its arguments. A scratch root requires a runner.

## Probe service (tests only)

The iPhone gate uses a disposable flatd fixture on `127.0.0.1:8799`. Point the test tunnel at that port and replace
`probe.example.net:8443` with the public test route. Create the identity directory once, then paste the A pairing
JSON into Arestia.

```bash
probe_dir="$HOME/.flatd-probe"
python3 home-front/client/probe_service.py make-identities "$probe_dir" --url https://probe.example.net:8443
python3 home-front/client/probe_service.py pairing-code "$probe_dir" --key a

probe_run() {
    local run_dir
    run_dir=$(mktemp -d "$probe_dir/run.XXXXXX") || return
    printf 'Probe log %s\n' "$run_dir/probe.log"
    python3 home-front/client/probe_service.py serve --dir "$probe_dir" --log "$run_dir/probe.log" "$@"
}
probe_run --key a
```

Use a fresh log for every serve run. `probe_run` creates a new log path each time, and `--log` refuses an existing
file. For the wrong-key run, stop the probe to close its live connections and run `probe_run --key b`, keeping
the A pairing on the phone. Run the direct WebSocket test and direct pinned POST test one at a time. Check the
new log entries after each test for its own fresh `tcp_accept` and a `tls_handshake` with `result: failed` for that
peer and port. The B run must have zero `request` entries. A test without a fresh accept and failure is inconclusive.
Stop B, run `probe_run --key a`, and confirm both direct tests succeed with the original pairing and appear in
the new A log.

The fixture uses TLS 1.2 so a client can signal certificate refusal during the handshake. Successful HTTP/1.1
requests can share the same connection, with 60 seconds idle and 10 seconds to read each request once it starts.
WebSocket upgrades clear the HTTP read deadline. Logs are JSON lines with a known method and decoded route or
`<other>`, plus the Bearer verdict. Arestia's unauthenticated health check logs `bearer: missing`.

Add `--delay /api/modes/cooking=20` to hold the Cooking response for 20 seconds. To time the Fans Shortcut, use
`--delay /api/devices/fan:probe=20`. The `/test/echo` WebSocket takes the dummy Bearer token and echoes text and
binary messages. Run `python3 home-front/client/probe_service.py --relay 8800 127.0.0.1:8799` in a separate
terminal for a plain TCP path to the TLS probe. The relay listens on loopback.

For home-route tests, add `--home-port 8801` and use
`python3 home-front/client/probe_service.py pairing-code "$probe_dir" --key h --url https://127.0.0.1:8801`.
With the dummy token, the H listener's `/api/remote` reads the saved URL and A certificate on each request,
including during a B run. It returns null fields if either file is missing or invalid. The URL needs an HTTPS
DNS name and explicit port.

Run `python3 -m unittest home-front/client/test_probe.py` to check the probe.
