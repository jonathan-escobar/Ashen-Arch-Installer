#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Ejecuta con sudo'; exit 1; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "$ROOT/build/profile/profiledef.sh" ]] || { echo 'Antes ejecuta bash scripts/prepare-profile.sh'; exit 1; }
mkdir -p "$ROOT/out" "$ROOT/build/work"
mkarchiso -v -w "$ROOT/build/work" -o "$ROOT/out" "$ROOT/build/profile"
