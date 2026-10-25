#!/bin/sh
# The only thing the Mac's backup key can run on the server (forced command of user empire-backup, installed to
# /usr/local/lib/empire-backup/serve by deploy/install-backup.sh). It lists and hands out the encrypted copies in the
# outbox, nothing else. Contract with aresync's backup.sh (docs/BACKUP.md):
#   list      one line per complete copy, oldest first: NAME<TAB>BYTES<TAB>SHA256<TAB>CREATED (ISO 8601, UTC)
#   get NAME  the file's bytes; an invalid or unknown name exits 2
set -eu

OUTBOX=/var/backups/empire/outbox
cmd="${SSH_ORIGINAL_COMMAND:-}"

case "$cmd" in
  list)
    for f in "$OUTBOX"/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].tar.gz.age; do
      # a copy counts once its checksum is written (empire_backup.py writes it last)
      [ -f "$f" ] && [ -f "$f.sha256" ] || continue
      printf '%s\t%s\t%s\t%s\n' "${f##*/}" "$(stat -c %s "$f")" "$(cut -d ' ' -f 1 "$f.sha256")" \
        "$(date -u -d "@$(stat -c %Y "$f")" +%Y-%m-%dT%H:%M:%SZ)"
    done
    ;;
  "get "*)
    name="${cmd#get }"
    case "$name" in
      [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].tar.gz.age) ;;
      *) echo "invalid name" >&2; exit 2 ;;
    esac
    if [ ! -f "$OUTBOX/$name" ] || [ ! -f "$OUTBOX/$name.sha256" ]; then
      echo "no such copy: $name" >&2; exit 2
    fi
    logger -t empire-backup "fetched $name" 2>/dev/null || true
    exec cat "$OUTBOX/$name"
    ;;
  *)
    echo "usage: list | get NAME" >&2; exit 2
    ;;
esac
