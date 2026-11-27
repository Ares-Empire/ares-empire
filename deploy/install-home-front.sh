#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# Keep the SSH policy transaction and front installation under the CLI's shared lock.
exec python3 "$repo/home-front/home-front" _install "$repo/deploy/systemd/haproxy-home-front.conf" "$@"
