#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Use sudo bash scripts/build-iso.sh' >&2; exit 1; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "$ROOT/build/profile/profiledef.sh" ]] || {
    echo 'Run bash scripts/prepare-profile.sh first' >&2; exit 1;
}
command -v mkarchiso >/dev/null || { echo 'Install archiso first' >&2; exit 1; }
mkdir -p "$ROOT/out" "$ROOT/build/work"
mkarchiso -v -w "$ROOT/build/work" -o "$ROOT/out" "$ROOT/build/profile"
