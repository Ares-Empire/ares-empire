# Backups

**Status (2026-10-25): live.** Every night the server makes a copy of the empire's data that cannot be rebuilt;
the MacBook fetches it with Aresync (Patrik's choice: free, no new provider; the Mac is the copy outside netcup).

## What is in a copy

Only what cannot be rebuilt. The code is on GitHub; the Arestoteles vault is pushed to GitHub every minute.

| Folder in the copy | What | From |
|---|---|---|
| `aresium/aresium.pgdump` | Patrik's Aresium database (transactions, categories, rules, corrections) | `pg_dump` of `aresium-db-1` |
| `aresium/personal.json` | Aresium's personal settings (git-ignored) | `/root/aresium/config/` |
| `accounts/data.db`, `auxiliary.db`, `storage/` | Empire accounts (PocketBase) | `/var/lib/empire-accounts/pb_data/` |
| `arestemis/arestemis.db` | searches, listings, matches, application texts | `/root/Arestemis/data/` |
| `arestemis/testset/`, `site-eval/` | the labelled test sets (listing texts with Claude's labels) and every test run's results, see Arestemis `docs/TEST-SET.md` | `/root/arestemis-eval/` |
| `aresus/aresus.db`, `machines.json` | uptime, incidents, sync runs; machine token hashes | `/root/aresus/` |
| `push/push.db` | push device registrations | `/var/lib/empire-push/` |
| `hub/state.json`, `sync-meta.json` | the hub's provinces and chronicle | `/root/ares-empire/data/` |
| `secrets/*.env`, `aresync-config` | every service's secrets and the server's Aresync settings | the services' `.env` files |
| `server/` | Caddyfile, the empire's systemd units, the server's Aresync deploy hooks | `/etc/caddy`, `/etc/systemd/system`, `/root/aresync/hooks` |
| `MANIFEST.json` | every file's size and SHA-256, row counts per table | made by the job |

Not in it, on purpose: the Arestoteles vault (GitHub), its search index and model (rebuilt), Docker images and Python
environments (rebuilt), the GitHub login and deploy keys (made again), and nametbd2, a separate project on the same
server that is not part of the empire.

**New data:** a service that starts storing data that cannot be rebuilt adds it to the lists at the top of
`backup/empire_backup.py` (`POSTGRES`, `SQLITE`, `FILES`, `DIRS`) and to this table, in the same change. A required file
that goes missing fails the nightly run on purpose, so a moved file is noticed the next morning.

## When and where

- **Server, 03:15 (±5 min):** `empire-backup.timer` runs `backup/empire_backup.py` straight from the checkout (a pulled
  change applies the next night). About a second; 3–4 MB, 0.7 MB encrypted (2026-10-25).
  - `/var/backups/empire/copies/YYYY-MM-DD/`: the plain copy, root only, the **7 newest** kept. For undoing a mistake.
  - `/var/backups/empire/outbox/YYYY-MM-DD.tar.gz.age` (+ `.sha256`): the same, encrypted, the **7 newest** kept.
- **Mac, 09:00 and at login:** Aresync fetches every outbox copy it does not have yet into
  `~/Backups/Ares Empire/copies/`, checks each one completely (size, SHA-256, decrypts it and compares every file with
  `MANIFEST.json`, without writing anything unencrypted to disk), then deletes old ones: it keeps the **7 newest**, the
  newest of each of the **4 newest weeks** and of the **6 newest months**, so at most about 6 months. If the Mac was
  off, it catches up on the days the server still has. Details: `aresync/README.md` → Backups (Mac).

## Encryption and access

- **age** (Debian package on the server, Homebrew on the Mac). The server has only the Mac's **public** key
  (`/etc/empire-backup/recipients.txt`): it can make copies but never read one.
- The **secret key** is in the Mac's login Keychain (item "Ares Empire backup key", account `age`) and must also be in
  Patrik's password manager: without it the Mac's copies cannot be opened. Show it with
  `security find-generic-password -s "Ares Empire backup key" -a age -w`.
- The Mac logs in as user `empire-backup` with `~/.ssh/empire_backup`. That key can only run `backup/serve.sh`
  (installed as `/usr/local/lib/empire-backup/serve`): `list` and `get NAME`, nothing else; no shell, no forwarding.
  The user's home and key file belong to root, so it cannot change that. Tested 2026-10-25: other commands, path tricks
  and an interactive login are refused.
- The server's OpenSSH briefly blocks an address after several failed logins, root logins from it included.

## Alerts

- **The server job fails:** the unit's result is "failed"; Aresus's check "Backups" in the Empire province turns it
  into an Issue and a push (once push works on the phone).
- **On the Mac** (Aresync problems → the Aresus report and its push): the fetch fails (alert from the second run on),
  a copy fails its check (at once), or the server's newest copy is older than 26 hours (at once: the nightly job has
  stopped).
- `journalctl -u empire-backup` shows each night's summary line; `journalctl -t empire-backup` each fetch by the Mac.

## Restore

### Undo a mistake on the server (from its own plain copies)

`D=/var/backups/empire/copies/YYYY-MM-DD` (the newest from before the mistake).

- **Aresium:** `systemctl stop aresium aresium-bot`, then
  `docker exec -i aresium-db-1 pg_restore -U aresium -d aresium --clean --if-exists --no-owner < $D/aresium/aresium.pgdump`,
  then start both. For single rows or tables, restore into a throwaway container first (as in the restore test below)
  and copy across what is needed.
- **A SQLite service:** stop it, copy the `.db` over the live one, delete the live `-wal`/`-shm` files, give the file
  back to the service's user, start it.

  | Data | Service | Live file | Owner |
  |---|---|---|---|
  | accounts | `empire-accounts` | `/var/lib/empire-accounts/pb_data/data.db` (+ `auxiliary.db`) | `empire-accounts` |
  | Arestemis | `arestemis` | `/root/Arestemis/data/arestemis.db` | root |
  | Aresus | `aresus` | `/root/aresus/data/aresus.db` | root |
  | push | `empire-push` | `/var/lib/empire-push/push.db` | `empire-push` |

- **Hub data:** copy `hub/state.json` back to `/root/ares-empire/data/` (served live, no restart).
- **Secrets and settings:** copy the file back and restart its service.

### From the Mac (the server or its data is gone)

1. `bash ~/aresync/restore-backup.sh ~/Backups/Ares\ Empire/copies/YYYY-MM-DD.tar.gz.age` decrypts the copy into a
   folder on the Desktop and checks every file against `MANIFEST.json`.
2. On a new server: Aresync clones the repos (its server setup in `aresync/README.md`); run the installers
   (`deploy/install-accounts.sh`, `install-push.sh`, `install-backup.sh`), put back the Caddyfile, the `.env` files and
   units from `server/`, then the data as above. Delete the decrypted folder afterwards.

### Restore test

2026-10-25, the first copy: the Aresium dump restored into a throwaway `postgres:16` container gave 1,246 transactions,
246 rules and 25 corrections, as live; every SQLite copy's row counts matched its manifest; the Mac fetched the
encrypted copy, decrypted it and all 40 files matched `MANIFEST.json`. Repeat after a new database joins the backup.

## Setup (done 2026-10-25) and a new Mac

1. On the Mac: `brew install age`; `age-keygen` and put the secret key into the Keychain item above (never into a file),
   and into the password manager; `ssh-keygen -t ed25519 -N "" -f ~/.ssh/empire_backup`.
2. On the server: `sudo bash deploy/install-backup.sh --mac <age public key> <file with the SSH public key>`. Without
   `--mac` it only updates (the Aresync hook runs it when `backup/serve.sh`, the installer or the units change).
3. In the Mac's `~/aresync/config`: `BACKUP_SSH="empire-backup@<the server's IP address>"`.

The privacy policy names the backups and how long they are kept (section 9, Speicherdauer / Storage period).
