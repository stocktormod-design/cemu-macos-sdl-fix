# SDL gamecontroller env helpers (merge, sanitize, export).

CEMU_SDL_CONFIG_KEY="SDL_GAMECONTROLLERCONFIG"
CEMU_SDL_CONFIG_FILE_KEY="SDL_GAMECONTROLLERCONFIG_FILE"

# Trailing commas (from strings-extract) break some SDL builds when loading a mapping file.
cemu_sdl_sanitize_mapping_line() {
	local line="${1//$'\r'/}"
	line="${line%%#*}"
	line="${line#"${line%%[![:space:]]*}"}"
	line="${line%"${line##*[![:space:]]}"}"
	while [[ "$line" == *, ]]; do
		line="${line%,}"
	done
	[[ -n "$line" ]] && printf '%s\n' "$line"
}

cemu_sdl_append_sources_to_file() {
	local out="$1"
	shift
	local src line
	: >"$out"
	for src in "$@"; do
		[[ -f "$src" ]] || continue
		while IFS= read -r line || [[ -n "$line" ]]; do
			cemu_sdl_sanitize_mapping_line "$line" >>"$out" || true
		done <"$src"
	done
}

# Newline-separated mappings for SDL_GAMECONTROLLERCONFIG (highest priority for Cemu).
cemu_sdl_patches_config() {
	local patch_file="$1"
	[[ -f "$patch_file" ]] || return 0
	cemu_sdl_append_sources_to_file /dev/stdout "$patch_file"
}

cemu_sdl_export_launch_env() {
	local app="${1:-}"
	local script_dir="${2:-}"
	local cemu_data="${3:-${HOME}/Library/Application Support/Cemu}"
	local db_bundled="${script_dir}/data/gamecontrollerdb.txt"
	local db_patch="${script_dir}/data/gamecontroller_patches.txt"
	local db_user="${cemu_data}/gamecontroller_user.txt"
	local cache="${cemu_data}/sdl_cache"
	local merged="${cache}/gamecontroller_merged.txt"

	mkdir -p "$cache"
	cemu_sdl_append_sources_to_file "$merged" "$db_bundled" "$db_patch" "$db_user"
	export "${CEMU_SDL_CONFIG_FILE_KEY}=${merged}"

	if [[ -f "$db_patch" ]]; then
		# shellcheck disable=SC2086
		export ${CEMU_SDL_CONFIG_KEY}="$(cemu_sdl_patches_config "$db_patch")"
	fi
}
