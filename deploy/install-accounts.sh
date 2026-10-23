#!/usr/bin/env bash
# Install or update Empire accounts (PocketBase). Safe to re-run.
#   sudo bash deploy/install-accounts.sh
# Updating PocketBase: change VERSION + SHA256 (from the release's checksums.txt), re-run.
# Data lives in /var/lib/empire-accounts and is never touched by this script.
set -euo pipefail

VERSION=0.40.6
SHA256=0e1f609158ed945f809f8a02ae012aa0427129c66ebb63c1aee76f2c0309373f
URL="https://github.com/pocketbase/pocketbase/releases/download/v${VERSION}/pocketbase_${VERSION}_linux_amd64.zip"

REPO="$(cd "$(dirname "$0")/.." && pwd)"
OPT=/opt/empire-accounts
DATA=/var/lib/empire-accounts

id empire-accounts >/dev/null 2>&1 ||
  useradd --system --home-dir "$DATA" --shell /usr/sbin/nologin empire-accounts
install -d -m 755 -o root -g root "$OPT"
install -d -m 700 -o empire-accounts -g empire-accounts "$DATA"

if [ "$("$OPT/pocketbase" --version 2>/dev/null)" != "pocketbase version $VERSION" ]; then
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  curl -fsSL -o "$tmp/pb.zip" "$URL"
  echo "$SHA256  $tmp/pb.zip" | sha256sum -c -
  python3 -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extract("pocketbase", sys.argv[2])' "$tmp/pb.zip" "$tmp"
  install -m 755 -o root -g root "$tmp/pocketbase" "$OPT/pocketbase"
fi

# Migrations are code (root-owned, read-only for the service).
rm -rf "${OPT:?}/pb_migrations"
cp -r "$REPO/accounts/pb_migrations" "$OPT/pb_migrations"
chown -R root:root "$OPT/pb_migrations"
chmod -R a+rX,go-w "$OPT/pb_migrations"

install -m 644 "$REPO/deploy/systemd/empire-accounts.service" /etc/systemd/system/empire-accounts.service
systemctl daemon-reload
systemctl enable empire-accounts >/dev/null 2>&1
systemctl restart empire-accounts
for _ in $(seq 1 20); do
  curl -fs -m 1 http://127.0.0.1:8090/api/health >/dev/null && { echo "empire-accounts $VERSION is up"; exit 0; }
  sleep 0.5
done
echo "empire-accounts did not come up; see: journalctl -u empire-accounts" >&2
exit 1
