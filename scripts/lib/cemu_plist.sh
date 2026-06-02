# Info.plist helpers for SDL fix (LSEnvironment — works from Dock/Launchpad).

CEMU_SDL_ENV_FILE_KEY="SDL_GAMECONTROLLERCONFIG_FILE"
CEMU_SDL_ENV_INLINE_KEY="SDL_GAMECONTROLLERCONFIG"
CEMU_SDL_ENV_KEY="$CEMU_SDL_ENV_FILE_KEY" # backwards compat
CEMU_SDL_MARKER=".cemu_sdl_fix_installed"
CEMU_SDL_MAPPINGS_NAME="cemu_sdl_mappings.txt"

cemu_plist_path() {
	printf '%s/Contents/Info.plist' "$1"
}

cemu_is_patched_v2() {
	local app="$1"
	[[ -f "${app}/Contents/Resources/${CEMU_SDL_MARKER}" ]] && return 0
	local plist
	plist="$(cemu_plist_path "$app")"
	/usr/libexec/PlistBuddy -c "Print :LSEnvironment:${CEMU_SDL_ENV_FILE_KEY}" "$plist" &>/dev/null
}

# PlistBuddy cannot set SDL_GAMECONTROLLERCONFIG (commas). Python plistlib can.
cemu_plist_set_sdl_environment() {
	local app="$1"
	local mappings_file="$2"
	local plist
	plist="$(cemu_plist_path "$app")"
	[[ -f "$plist" ]] || return 1

	# Use -c (not <<PY heredoc) so piped patch text reaches sys.stdin.
	CEMU_PLIST_PATH="$plist" CEMU_MAPPINGS_PATH="$mappings_file" python3 -c '
import os
import plistlib
import sys

plist_path = os.environ["CEMU_PLIST_PATH"]
mappings_file = os.environ["CEMU_MAPPINGS_PATH"]
inline = sys.stdin.read().rstrip("\n")

with open(plist_path, "rb") as f:
    pl = plistlib.load(f)

le = pl.setdefault("LSEnvironment", {})
le["SDL_GAMECONTROLLERCONFIG_FILE"] = mappings_file
if inline:
    le["SDL_GAMECONTROLLERCONFIG"] = inline
else:
    le.pop("SDL_GAMECONTROLLERCONFIG", None)

with open(plist_path, "wb") as f:
    plistlib.dump(pl, f)
'
}

# Deprecated name — kept for older callers.
cemu_plist_set_sdl_mappings() {
	cemu_plist_set_sdl_environment "$1" "$2" </dev/null
}

cemu_plist_clear_sdl_mappings() {
	local app="$1"
	local plist
	plist="$(cemu_plist_path "$app")"
	[[ -f "$plist" ]] || return 0

	CEMU_PLIST_PATH="$plist" python3 - <<'PY'
import os
import plistlib

plist_path = os.environ["CEMU_PLIST_PATH"]
with open(plist_path, "rb") as f:
    pl = plistlib.load(f)

le = pl.get("LSEnvironment")
if isinstance(le, dict):
    le.pop("SDL_GAMECONTROLLERCONFIG_FILE", None)
    le.pop("SDL_GAMECONTROLLERCONFIG", None)
    if not le:
        pl.pop("LSEnvironment", None)

with open(plist_path, "wb") as f:
    plistlib.dump(pl, f)
PY
}

cemu_app_resign() {
	local app="$1"
	command -v codesign >/dev/null 2>&1 || return 0
	xattr -cr "$app" 2>/dev/null || true
	codesign --force --deep --sign - "$app" 2>/dev/null
}
