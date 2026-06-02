#!/usr/bin/env bash
# Install SDL mappings: Mach-O launcher (Dock) + Info.plist LSEnvironment (backup).
#
#   ./scripts/install_cemu_sdl_fix.sh --force   # fix after old broken wrapper install
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[[ -n "${CEMU_SDL_FIX_ROOT:-}" ]] && SCRIPT_DIR="$CEMU_SDL_FIX_ROOT"
# shellcheck source=lib/cemu_discover.sh
source "${SCRIPT_DIR}/lib/cemu_discover.sh"
# shellcheck source=lib/cemu_plist.sh
source "${SCRIPT_DIR}/lib/cemu_plist.sh"
source "${SCRIPT_DIR}/lib/cemu_sdl_mappings.sh"
source "${SCRIPT_DIR}/lib/cemu_launcher.sh"
CEMU_SDL_FIX_ROOT="${SCRIPT_DIR}"

BUNDLED_DB="${SCRIPT_DIR}/data/gamecontrollerdb.txt"
BUNDLED_PATCH="${SCRIPT_DIR}/data/gamecontroller_patches.txt"
DB_USER="${HOME}/Library/Application Support/Cemu/gamecontroller_user.txt"

LIST_ONLY=0
FORCE=0
INSTALL_ALL=1
EXPLICIT_APP=""

while [[ $# -gt 0 ]]; do
	case "$1" in
		--all) INSTALL_ALL=1; shift ;;
		--one|--metal-only) INSTALL_ALL=0; shift ;;
		--list|-l) LIST_ONLY=1; shift ;;
		--force|-f) FORCE=1; shift ;;
		--help|-h) sed -n '2,12p' "$0"; exit 0 ;;
		-*) echo "Unknown option: $1" >&2; exit 1 ;;
		*) EXPLICIT_APP="$1"; INSTALL_ALL=0; shift ;;
	esac
done

[[ -f "$BUNDLED_DB" ]] || { echo "Missing $BUNDLED_DB" >&2; exit 1; }

merge_mappings_file() {
	local out="$1"
	cemu_sdl_append_sources_to_file "$out" "$BUNDLED_DB" "$BUNDLED_PATCH" "$DB_USER"
}

apply_plist_and_sign() {
	local app="$1" mappings="$2"
	cemu_sdl_patches_config "$BUNDLED_PATCH" | cemu_plist_set_sdl_environment "$app" "$mappings"
	if cemu_app_resign "$app"; then
		echo "  → codesign OK (required after plist edit)"
	else
		echo "  ⚠ codesign failed — right-click Cemu → Open, or: xattr -cr \"$app\"" >&2
	fi
}

install_into_app() {
	local app="$1"
	local res="${app}/Contents/Resources"
	local mappings="${res}/${CEMU_SDL_MAPPINGS_NAME}"
	local label name

	label="$(basename "$app")"
	cemu_can_patch "$app" || {
		echo "✗ Read-only (cannot patch): $label" >&2
		return 1
	}

	# Always restore Mach-O as CFBundleExecutable (old v1 used bash wrapper — breaks Dock)
	if cemu_restore_mach_o_launcher "$app" >/dev/null; then
		echo "  → restored real Cemu binary (removed old bash wrapper)"
	fi

	name="$(cemu_find_launcher_name "$app")" || {
		echo "✗ Could not find launcher binary in $label" >&2
		return 1
	}

	local was_patched=0
	cemu_is_patched_v2 "$app" && was_patched=1

	mkdir -p "$res"
	merge_mappings_file "$mappings"
	local bad=0
	bad="$(grep -c ',$' "$mappings" 2>/dev/null | head -1 | tr -d '[:space:]')"
	bad="${bad:-0}"
	[[ "${bad:-0}" -eq 0 ]] || echo "  ⚠ warning: ${bad} mapping lines with invalid trailing comma" >&2

	apply_plist_and_sign "$app" "$mappings"
	cemu_install_sdl_launcher "$app" "$BUNDLED_PATCH" || return 1
	cemu_app_resign "$app" >/dev/null || true

	# Cleanup v1 files
	rm -f "${res}/gamecontrollerdb.txt" "${res}/gamecontroller_patches.txt" \
		"${res}/.cemu_sdl_fix_launcher"

	printf 'v2-plist %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" >"${res}/${CEMU_SDL_MARKER}"

	if [[ $was_patched -eq 1 ]]; then
		echo "✓ Updated: $label ($name)"
	else
		echo "✓ Installed: $label ($name)"
	fi
	echo "    Launch Cemu from Dock (Mach-O launcher sets SDL env)"
	echo "    $(wc -l <"$mappings" | tr -d ' ') mapping lines"
}

apps=()
if [[ -n "$EXPLICIT_APP" ]]; then
	while IFS= read -r app; do [[ -n "$app" ]] && apps+=("$app"); done < <(cemu_discover_apps "$EXPLICIT_APP")
elif [[ $INSTALL_ALL -eq 1 ]]; then
	while IFS= read -r app; do [[ -n "$app" ]] && apps+=("$app"); done < <(cemu_discover_apps)
else
	while IFS= read -r app; do [[ -n "$app" ]] && apps+=("$app"); done < <(cemu_discover_apps)
	if [[ ${#apps[@]} -gt 1 ]]; then
		for a in "${apps[@]}"; do
			[[ "$(basename "$a")" == *[Mm]etal* ]] && apps=("$a") && break
		done
	fi
fi

[[ ${#apps[@]} -gt 0 ]] || { echo "No Cemu.app found." >&2; exit 1; }

if [[ $LIST_ONLY -eq 1 ]]; then
	for a in "${apps[@]}"; do
		n="$(cemu_find_launcher_name "$a")"
		t=""
		cemu_is_patched_v2 "$a" && t=" [SDL-fix]"
		echo "  $(basename "$a") (${n})${t}"
		echo "    $a"
	done
	exit 0
fi

echo "Installing SDL fix into ${#apps[@]} app(s) …"
echo ""

ok=0 fail=0
for a in "${apps[@]}"; do
	install_into_app "$a" && ok=$((ok + 1)) || fail=$((fail + 1))
	echo ""
done

echo "Done: $ok succeeded, $fail failed."
echo ""
echo "Open Cemu from Dock as usual. ./scripts/launch_cemu.sh is optional (debug)."

[[ $fail -eq 0 ]]
