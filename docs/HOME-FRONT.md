# Home-front

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
   at the end of `/etc/ssh/sshd_config`. It also installs the server front described below. The only other allowed Include is Debian's
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
  process checks one second apart before printing `CLOSED (verified)`. For a listen account it also verifies that
  its ports stopped listening. If the account has public routes, removal runs their route-off operation before
  expiring the account and includes the public front's closure outcome in its result.
  If it prints `REVOCATION UNCONFIRMED`, follow the printed next step.
- To re-add an expired account with the same kind and ports, run `add-machine` with its public key. Expiry is
  cleared after the key and reloaded policy have been verified and the marker removal has been synced.
  For a different key on an active account, run `remove-machine` first and wait for `CLOSED (verified)`.
  Repeating the same key leaves its key file in place.

## Server front

Home-front alone manages `haproxy.service` on this server. Its `FragmentPath` must be Debian's
`/usr/lib/systemd/system/haproxy.service`. Its `DropInPaths` must contain exactly
`/etc/systemd/system/haproxy.service.d/home-front.conf` and, while the acceptance fixture runs,
`/run/systemd/system/haproxy.service.d/zz-home-front-acceptance.conf`. Systemd must report
`NeedDaemonReload=no`. Run manual
`systemctl start/stop/reload/restart haproxy` commands only between `home-front` commands.

Before installing, check that TCP 8443 is free, that the provider allows it on IPv4 and IPv6, and that UFW is
configured with `IPV6=yes`. Hold the admin SSH session as described above.

1. Run `sudo bash deploy/install-home-front.sh`. If HAProxy is missing, the installer installs the home-front
   program and drop-in and reloads systemd. It prints the APT handoff only when the routes file is absent,
   the front lock is verified, or every retained route is off. Package removal can leave routes behind.
   If the installer names retained routes that are still on, edit `/etc/home-front/routes` as root under
   `/run/home-front.lock`, change the final field of each named row to `off`, then rerun the installer.
2. If prompted to install HAProxy, run the entire read-only check as root before using APT.

   ```bash
   sudo bash <<'BASH'
   set -euo pipefail
   systemctl show -p DropInPaths -p FragmentPath haproxy.service
   unit_path=$(systemctl show -p UnitPath --value)
   read -r -a unit_dirs <<< "$unit_path"
   (( ${#unit_dirs[@]} ))
   python3 - "${unit_dirs[@]}" <<'PY'
   from pathlib import Path
   import sys

   managed = Path("/etc/systemd/system/haproxy.service.d/home-front.conf")
   matches = []
   for directory in map(Path, sys.argv[1:]):
       try:
           entries = list(directory.iterdir())
       except FileNotFoundError:
           continue
       for entry in entries:
           if entry.name == "haproxy.service":
               matches.append(entry)
           elif entry.name in ("haproxy.service.d", "service.d"):
               matches.extend(path for path in entry.iterdir() if path.suffix == ".conf")
   for path in sorted(matches):
       print(path)
   if managed not in matches:
       sys.exit(f"Managed drop-in missing from unit search paths: {managed}")
   PY
   BASH
   ```

   The scan skips absent optional unit directories. Stop on any inspection error.
   `FragmentPath` must be empty or `/usr/lib/systemd/system/haproxy.service`.
   The only drop-in must be `/etc/systemd/system/haproxy.service.d/home-front.conf`. On a fresh host,
   systemd can leave both properties empty until the package provides the base unit. The disk scan must
   still find the managed drop-in and may also list Debian's unit file. [systemd service loader](https://github.com/systemd/systemd/blob/v257/src/core/service.c#L829-L834) · [Unit loader](https://github.com/systemd/systemd/blob/v257/src/core/unit.c#L1265-L1289)

   Once the check passes, run `sudo apt-get install haproxy`, then run
   `sudo bash deploy/install-home-front.sh` again. On a fresh setup, the package's own start invokes the
   staged render hook. The routes and config files are still absent, so render fails and HAProxy stays down
   until the installer creates them on the second run.
   If `systemctl show -p Result haproxy.service` reports `Result=start-limit-hit` after that run, check that
   the routes and config files and the managed drop-in are in place, run
   `sudo systemctl reset-failed haproxy.service`, then rerun the installer.

With the package installed, the installer verifies the effective unit before any start. A definition mismatch
stops and disables HAProxy, even when routes are on, and the installer checks shutdown before reporting the
mismatch. The installer refuses a masked unit and preserves its mask.

The installer disables and stops a locked front and prints the recovery command. With an unlocked front and every route off,
it enables and restarts HAProxy and verifies that it answers no name. With an unlocked front and any route on,
it leaves the running front as it is. Installation requires the expected unit paths and exact managed start and
reload commands.

The installer preserves existing IPv4 and IPv6 UFW rules for `8443/tcp`. It adds missing rules only after
verifying the locked front is stopped or the unlocked front serves no routes. If routes are on and ingress
rules are missing, run `home-front off` and verify closure before retrying the installer.

Set the private wildcard zone in `/etc/home-front/config` (root-owned, mode `0600`). The installer seeds it with
`zone = home.example.net`. Add wildcard A and AAAA records for that zone pointing to the server. HAProxy routes
TLS by SNI and passes it through to the home service. Keep each route URL private. The home service presents a
self-signed certificate with its own identity. Never issue a certificate for the wildcard or a route name.

```bash
sudo home-front route probe tunnel-test 20099
sudo home-front on probe
sudo home-front status
sudo home-front off probe
```

- `route <service> <account> <port>` creates an off route on a fixed service port (20001–20099) of an activated,
  provisioned listen account and prints its URL once. The passwd policy record grants the port. Route authorization
  uses the provisioned record even if the machines file changes. Save the URL privately. The root-owned routes
  file `/etc/home-front/routes` has mode `0600`. The start hook logs and omits unauthorized rows. The reload hook
  and `on` refuse while any recorded-on row is unauthorized and name the `off` command to run. Both hooks fail
  if an account file cannot be read or the routes file is malformed.
- `on <service>` enables the route. Both `route` and `on` reload the running front and leave current streams open.
  If activation is unconfirmed, the route may already be recorded on and a later start or reload can apply it.
  Run `off <service>` to verify closure.
- `off <service>` closes one route. Use `off` without a service to close every route. A normal closure restarts
  the whole front and ends its streams, including streams from older workers. Clients on other routes can reconnect.
  The SSH tunnel keeps running. `off` first persists the selected routes as off, then checks the managed commands
  before restarting. If a step fails, fallback writes the front lock, then always attempts stop, disable and kill.
  Once shutdown is verified, fallback writes and reads back an empty front even if the lock failed. It checks
  shutdown again and repeats stop, disable and kill once if a start intervened. It checks the managed unit again
  before reporting the outcome. An `off` interrupted before fallback must be rerun to verify closure.
- `status` shows the front lock, each route's on/off state and whether its tunnel port is listening. While locked,
  every route is shown as off. While unlocked, it marks recorded-on rows that the next start would omit.

| Exit | Outcome | What was verified |
| --- | --- | --- |
| 0 | `CLOSED (verified)` | The routes file is on disk with the selected routes off. Every front process started after the restart, no HAProxy process exists outside the unit, and the rendered files match. Connections to the selected backend ports are gone and the selected names return zero bytes. |
| 2 | `CLOSED (verified): all routes; the front is locked` | The lock is durable and reads back. Before and after writing the empty front, systemd reports HAProxy disabled and stopped (inactive or failed), the process census is empty, and 8443 has no listener. The zero-route configuration and empty map are durable and read back. The final unit paths and managed hooks match. |
| 3 | `REVOCATION UNCONFIRMED` | Closure could not be verified. Stop `flat-remote` on the home machine. |

With the front locked, `on` and `route` refuse. After verified fallback, the managed unit starts with an empty front.
Fix the cause reported by `off`, then run `sudo home-front reconcile`. It persists every route off, enables HAProxy,
checks its effective unit again before restarting, and verifies that the names return zero bytes before removing
the lock and reloading.
Rerun `reconcile` after an interruption. Restore each intended route with `on <service>`.

The systemd start and reload hooks rebuild and check the HAProxy configuration and map in `/etc/haproxy`.
Fallback is the only write outside those hooks. It writes zero routes after verifying that the front has stopped.
Route changes, account changes and installation share `/run/home-front.lock`. The systemd render hook runs without
taking that lock.

### Limits

- If `SIGKILL` interrupts `off` between the lock and shutdown, the old worker can serve until the next start or `off`. No verified outcome was printed. Run `off` again.
- A successful state-directory `fsync` is the proof that the lock is on disk. This relies on the disk honoring a successful sync.
- Route authorization reads only `/etc/passwd`, `/etc/shadow` and `/etc/group`. Accounts found only through another name service are ineligible. Any expiry denies routes, including a future expiry that `add-machine` still treats as active for SSH.
- SSH account commands and the account lines of `status` still use `getent`. A failed lookup there leaves routes unchanged or closes them, and results in a refusal, a rollback or `REVOCATION UNCONFIRMED`.
- The routes file is the source of truth. A hand-written `on` for an authorized row is served at the next start. Edit it only under the lock, or use `on` and `off`.
- `status` reports recorded states and what the next start would omit. Use `off` to verify closure.
- The name probe checks for zero bytes, which also occurs when a tunnel is down. Closure rests on the routes file,
  process census and rendered files. The paced probe replaces the earlier H8 limit of 20 routes. It checks every
  selected name on both address families, with at least 0.5 seconds between connections. A verified normal `off`
  returns exit 0 at any route count.
- The process census covers the unit's control group and processes named `haproxy`. It misses a renamed copy started outside the unit.
- If stop fails while the unit stays active, killing HAProxy causes systemd to start it again because it has
  `Restart=always`. With the managed hooks and a persisted lock, that start serves no routes. If the unit
  stays active, `off` returns exit 3.
- Exit 2 means subsequent starts serve no routes. A manual start or a package upgrade can still start the empty front.
- `off` closes the public name. A process on the server can still reach `127.0.0.1:<port>` while the tunnel is up.


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

`python3 -m unittest discover -s home-front` exercises SSH policy, the installer, and the front with a scratch filesystem and an
injected command runner. `HOME_FRONT_ROOT` redirects managed paths, including the lock.
`HOME_FRONT_RUNNER` receives the command name followed by its arguments. A scratch root requires a runner.

## Server-front acceptance

Run on the lead's dedicated fixture front with the two `tunnel-test` ports configured as above and with the
wildcard DNS records in place. The server phases use intentional route and render faults and require reboots.
If acceptance reports `REVOCATION UNCONFIRMED`, terminate the dedicated `tunnel-test` SSH session on the Mac before investigating.
If a server phase is killed (a dropped SSH connection sends it SIGHUP), the front can be left half-changed, with a
fixture route still served. Recover before anything else, in this order:
- Terminate the dedicated `tunnel-test` SSH session on the Mac, so nothing answers behind the fixture routes.
- As root, make sure the phase is gone: `pgrep -af 'python3 - |home-front'` lists the phase (`python3 - <phase>`) and
  its `home-front` children. Stop what it lists and check again until it lists nothing.
- `chattr -i /etc/home-front/routes`; remove `/run/systemd/system/haproxy.service.d/zz-home-front-acceptance.conf` and
  `/root/home-front-acceptance-*`; run `systemctl daemon-reload`, then `systemctl reset-failed haproxy.service` (if it
  says the unit is not loaded, go on).
- Run `home-front off` and require `CLOSED (verified)` (with or without the front locked), then `home-front reconcile`.
- Reconnect the Mac tunnel and start that phase again from its preparation step.

1. On the Mac, run `bash home-front/acceptance-front.sh mac-fixture` (set `OPENSSL=` to pick the `openssl` that makes its certificate).
   Hold the SSH forwards printed by the script using the disposable `tunnel-test` key, and reconnect them after
   each server reboot. Keep the TLS fixture running while switching the Mac to the phone hotspot.
2. As root on the server, run `bash home-front/acceptance-front.sh prepare`, then `normal` and `overlap` as
   separate invocations of the script. Run the printed outside checks on the Mac from the hotspot and pass all
   expected private Caddy site URLs.
3. Run `bash home-front/acceptance-front.sh stale-prepare`, reboot, reconnect the tunnel and run `stale-check`.
4. Run `bash home-front/acceptance-front.sh fault write`, reboot, reconnect the tunnel and run `fault-check`.
   Reboot once more and run `post-reboot`. Repeat this sequence for `fault render` and `fault write-all`.
   Pass the same Caddy site URLs to the final outside check.

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
