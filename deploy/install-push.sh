#!/usr/bin/env bash
# Install or update the Empire push service. Re-run after changes in push/ or its shared Python modules.
#   sudo bash deploy/install-push.sh
# Code and venv go to /opt/empire-push (root-owned, read-only for the service), data to /var/lib/empire-push
# (never touched here), the APNs key (once there is one) to /etc/empire-push. See docs/PUSH.md → Operating.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
OPT=/opt/empire-push
DATA=/var/lib/empire-push
KEYS=/etc/empire-push

id empire-push >/dev/null 2>&1 ||
  useradd --system --home-dir "$DATA" --shell /usr/sbin/nologin empire-push
install -d -m 755 -o root -g root "$OPT"
install -d -m 700 -o empire-push -g empire-push "$DATA"
install -d -m 750 -o root -g empire-push "$KEYS"

# Python packages: reinstalled only when push/requirements.txt changed.
[ -x "$OPT/venv/bin/python" ] || python3 -m venv "$OPT/venv"
if ! cmp -s "$REPO/push/requirements.txt" "$OPT/venv/requirements.txt"; then
  "$OPT/venv/bin/pip" install --quiet --disable-pip-version-check -r "$REPO/push/requirements.txt"
  install -m 644 "$REPO/push/requirements.txt" "$OPT/venv/requirements.txt"
fi

# The code (without its tests), root-owned and read-only for the service.
rm -rf "${OPT:?}/push.new"
install -d -m 755 "$OPT/push.new"
find "$REPO/push" -maxdepth 1 -name '*.py' ! -name 'test_*' -exec install -m 644 {} "$OPT/push.new/" \;
rm -rf "${OPT:?}/push"
mv "$OPT/push.new" "$OPT/push"
install -m 644 "$REPO/empire_language.py" "$OPT/empire_language.py"
install -m 644 "$REPO/empire_http.py" "$OPT/empire_http.py"

install -m 644 "$REPO/deploy/systemd/empire-push.service" /etc/systemd/system/empire-push.service
systemctl daemon-reload
systemctl enable empire-push >/dev/null 2>&1
systemctl restart empire-push
for _ in $(seq 1 20); do
  if health="$(curl -fs -m 1 http://127.0.0.1:8096/health)"; then
    echo "empire-push is up: $health"
    exit 0
  fi
  sleep 0.5
done
echo "empire-push did not come up; see: journalctl -u empire-push" >&2
exit 1
