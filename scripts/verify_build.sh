#!/usr/bin/env bash
# Rebuild Mach-O launchers from source and print SHA-256 for release verification.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${ROOT}/scripts/bin"
SRC="${ROOT}/scripts/cemu_sdl_launcher/launcher.c"

echo "=== Rebuilding launchers from launcher.c ==="
"${ROOT}/scripts/build_cemu_sdl_launcher.sh"

echo ""
echo "=== SHA-256 (compare with RELEASE_CHECKSUMS.txt) ==="
if command -v shasum >/dev/null 2>&1; then
	shasum -a 256 "${BIN}/cemu_sdl_launcher_arm64" "${BIN}/cemu_sdl_launcher_x86_64"
elif command -v sha256sum >/dev/null 2>&1; then
	sha256sum "${BIN}/cemu_sdl_launcher_arm64" "${BIN}/cemu_sdl_launcher_x86_64"
fi

echo ""
echo "=== file(1) ==="
file "${BIN}/cemu_sdl_launcher_arm64" "${BIN}/cemu_sdl_launcher_x86_64"

echo ""
echo "OK — inspect source: ${SRC}"
