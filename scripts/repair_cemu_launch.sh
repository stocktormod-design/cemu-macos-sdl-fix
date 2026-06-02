#!/usr/bin/env bash
# Fix "appen har ikke tillatelse til å åpne null" after SDL fix install.
# Cause: Info.plist was edited → broken code signature until re-signed.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "${SCRIPT_DIR}/install_cemu_sdl_fix.sh" --force --all
