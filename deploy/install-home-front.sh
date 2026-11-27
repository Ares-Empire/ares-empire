#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# The CLI shares the same lock and checked reload transaction with render.
exec python3 "$repo/home-front/home-front" _install "$@"
