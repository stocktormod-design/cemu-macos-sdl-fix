#!/usr/bin/env bash
# Optional: start Cemu with SDL mappings (same as plist install, via shell env).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[[ -n "${CEMU_SDL_FIX_ROOT:-}" ]] && SCRIPT_DIR="$CEMU_SDL_FIX_ROOT"
source "${SCRIPT_DIR}/lib/cemu_discover.sh"
source "${SCRIPT_DIR}/lib/cemu_plist.sh"
source "${SCRIPT_DIR}/lib/cemu_sdl_mappings.sh"

LIST_ONLY=0
EXPLICIT_APP=""
CEMU_PREFER="${CEMU_PREFER:-}"

while [[ $# -gt 0 ]]; do
	case "$1" in
		--list|-l) LIST_ONLY=1; shift ;;
		--metal) CEMU_PREFER=Metal; shift ;;
		--vanilla|--desktop) CEMU_PREFER=Cemu.app; shift ;;
		--help|-h) sed -n '2,10p' "$0"; exit 0 ;;
		-*) echo "Unknown: $1" >&2; exit 1 ;;
		*) EXPLICIT_APP="$1"; shift ;;
	esac
done

choose_app() {
	local -a apps=()
	while IFS= read -r a; do [[ -n "$a" ]] && apps+=("$a"); done < <(cemu_discover_apps "${EXPLICIT_APP:-}")
	[[ ${#apps[@]} -gt 0 ]] || { echo "No Cemu.app found." >&2; exit 1; }
	if [[ -n "$CEMU_PREFER" ]]; then
		local a
		for a in "${apps[@]}"; do
			[[ "$(basename "$a")" == *"${CEMU_PREFER}"* ]] && printf '%s\n' "$a" && return 0
		done
	fi
	printf '%s\n' "${apps[0]}"
}

if [[ $LIST_ONLY -eq 1 ]]; then
	cemu_discover_apps "${EXPLICIT_APP:-}" | while IFS= read -r app; do
		[[ -z "$app" ]] && continue
		n="$(cemu_find_launcher_name "$app")"
		t=""
		cemu_is_patched_v2 "$app" && t=" [SDL-fix plist]"
		echo "  $(basename "$app") (${n})${t}"
	done
	exit 0
fi

APP="$(choose_app)"
BIN="$(cemu_app_to_binary "$APP")"

# Always: sanitized merged file + inline patches (worked before plist-only CONFIG_FILE).
cemu_sdl_export_launch_env "$APP" "$SCRIPT_DIR"

echo "Launching $(basename "$APP") …"
echo "  SDL_GAMECONTROLLERCONFIG_FILE=${SDL_GAMECONTROLLERCONFIG_FILE}"
echo "  SDL_GAMECONTROLLERCONFIG=${#SDL_GAMECONTROLLERCONFIG} chars (device patches)"
exec "$BIN" "$@"
