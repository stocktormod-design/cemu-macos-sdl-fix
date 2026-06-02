#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[[ -n "${CEMU_SDL_FIX_ROOT:-}" ]] && SCRIPT_DIR="$CEMU_SDL_FIX_ROOT"
source "${SCRIPT_DIR}/lib/cemu_discover.sh"
source "${SCRIPT_DIR}/lib/cemu_plist.sh"
source "${SCRIPT_DIR}/lib/cemu_launcher.sh"

EXPLICIT_APP=""
while [[ $# -gt 0 ]]; do
	case "$1" in
		--help|-h) sed -n '2,3p' "$0"; exit 0 ;;
		-*) echo "Unknown: $1" >&2; exit 1 ;;
		*) EXPLICIT_APP="$1"; shift ;;
	esac
done

uninstall_app() {
	local app="$1"
	local res="${app}/Contents/Resources"

	cemu_remove_sdl_launcher "$app"
	cemu_plist_clear_sdl_mappings "$app"
	cemu_app_resign "$app" >/dev/null || true
	rm -f "${res}/${CEMU_SDL_MAPPINGS_NAME}" "${res}/${CEMU_SDL_MARKER}" \
		"${res}/gamecontrollerdb.txt" "${res}/gamecontroller_patches.txt" \
		"${res}/.cemu_sdl_fix_launcher"
	echo "✓ Fjernet fra: $(basename "$app")"
}

apps=()
while IFS= read -r a; do [[ -n "$a" ]] && apps+=("$a"); done < <(cemu_discover_apps "${EXPLICIT_APP:-}")
[[ ${#apps[@]} -gt 0 ]] || { echo "Fant ingen Cemu.app." >&2; exit 1; }

for a in "${apps[@]}"; do uninstall_app "$a"; done
