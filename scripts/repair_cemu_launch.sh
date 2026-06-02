#!/usr/bin/env bash
# Fix macOS "cannot open null" after SDL fix (broken signature until re-sign).
# Cause: Info.plist was edited → broken code signature until re-signed.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "${SCRIPT_DIR}/install_cemu_sdl_fix.sh" --force --all
