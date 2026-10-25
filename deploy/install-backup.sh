#!/usr/bin/env bash
# Install or update the nightly backup (docs/BACKUP.md). The aresync hook re-runs it when backup/serve.sh, this file
# or the units change; empire_backup.py itself runs from the checkout and needs no install.
#   sudo bash deploy/install-backup.sh                                     # update
#   sudo bash deploy/install-backup.sh --mac AGE_PUBLIC_KEY SSH_PUBKEY_FILE   # first install, or a new Mac
# The Mac's two public keys: its age key (the server encrypts every copy to it and can never decrypt one) and the
# SSH key aresync logs in with (it may only run backup/serve.sh).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME=empire-backup
HOME_DIR=/var/lib/empire-backup
CONF=/etc/empire-backup
SERVE=/usr/local/lib/empire-backup/serve

command -v age >/dev/null || DEBIAN_FRONTEND=noninteractive apt-get install -y -q age >/dev/null

# The Mac logs in as this user. sshd runs the forced command through the login shell, so it needs /bin/sh; it has
# no password, and its home and key file belong to root, so it cannot change its own restrictions.
id "$USER_NAME" >/dev/null 2>&1 ||
  useradd --system --home-dir "$HOME_DIR" --no-create-home --shell /bin/sh "$USER_NAME"
install -d -m 755 -o root -g root "$HOME_DIR" "$HOME_DIR/.ssh" "$(dirname "$SERVE")"
install -d -m 755 -o root -g root "$CONF"
install -m 755 -o root -g root "$REPO/backup/serve.sh" "$SERVE"

if [ "${1:-}" = "--mac" ]; then
  age_key="${2:?age public key missing}"; ssh_file="${3:?SSH public key file missing}"
  case "$age_key" in age1*) ;; *) echo "not an age public key: $age_key" >&2; exit 1 ;; esac
  ssh_key="$(head -n 1 "$ssh_file")"
  case "$ssh_key" in ssh-ed25519\ *) ;; *) echo "not an ed25519 public key: $ssh_file" >&2; exit 1 ;; esac
  printf '%s\n' "$age_key" >"$CONF/recipients.txt"
  printf 'restrict,command="%s" %s\n' "$SERVE" "$ssh_key" >"$HOME_DIR/.ssh/authorized_keys"
  chmod 644 "$CONF/recipients.txt" "$HOME_DIR/.ssh/authorized_keys"
fi
[ -s "$CONF/recipients.txt" ] || echo "note: no Mac key yet; run again with --mac (docs/BACKUP.md → Setup)" >&2

install -m 644 "$REPO/deploy/systemd/empire-backup.service" /etc/systemd/system/empire-backup.service
install -m 644 "$REPO/deploy/systemd/empire-backup.timer" /etc/systemd/system/empire-backup.timer
systemctl daemon-reload
systemctl enable --now empire-backup.timer >/dev/null 2>&1
echo "empire-backup installed:"
systemctl list-timers empire-backup.timer --no-legend
