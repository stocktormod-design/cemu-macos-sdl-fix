# Install Mach-O SDL env launcher as CFBundleExecutable (Dock-safe).

CEMU_SDL_PATCHES_INLINE_NAME="cemu_sdl_patches_inline.txt"

cemu_launcher_bin_for_exe() {
	local exe="$1"
	local probe="$exe"
	local arch=""
	[[ -f "${exe}.real" ]] && probe="${exe}.real"
	if file -b "$probe" 2>/dev/null | grep -q 'arm64'; then
		arch=arm64
	elif file -b "$probe" 2>/dev/null | grep -Eq 'x86_64|i386'; then
		arch=x86_64
	else
		return 1
	fi
	local root="${CEMU_SDL_FIX_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
	# install from repo: scripts/bin — from CemuSDLFix.app kit: kit root bin/
	for candidate in "${root}/bin/cemu_sdl_launcher_${arch}" "${root}/scripts/bin/cemu_sdl_launcher_${arch}"; do
		[[ -x "$candidate" ]] && printf '%s\n' "$candidate" && return 0
	done
	printf '%s/bin/cemu_sdl_launcher_%s\n' "$root" "$arch"
}

cemu_install_sdl_launcher() {
	local app="$1"
	local patch_src="$2"
	local name macos exe real launcher res
	local -r marker_name=".cemu_sdl_launcher_active"

	name="$(cemu_find_launcher_name "$app")" || return 1
	macos="${app}/Contents/MacOS"
	exe="${macos}/${name}"
	real="${macos}/${name}.real"
	res="${app}/Contents/Resources"

	[[ -f "$exe" ]] || return 1

	if [[ -f "${res}/${marker_name}" && -f "$real" && -x "$exe" ]]; then
		file -b "$exe" 2>/dev/null | grep -q 'Mach-O' || return 0
	fi

	launcher="$(cemu_launcher_bin_for_exe "$exe")" || {
		echo "  ✗ Ukjent arkitektur for $name — kjør: ./scripts/build_cemu_sdl_launcher.sh" >&2
		return 1
	}
	[[ -x "$launcher" ]] || {
		echo "  ✗ Mangler $launcher — kjør: ./scripts/build_cemu_sdl_launcher.sh" >&2
		return 1
	}

	if [[ ! -f "$real" ]]; then
		mv "$exe" "$real"
	fi

	cp -f "$launcher" "$exe"
	chmod +x "$exe"
	if [[ -f "$patch_src" ]]; then
		# shellcheck source=cemu_sdl_mappings.sh
		source "$(dirname "${BASH_SOURCE[0]}")/cemu_sdl_mappings.sh"
		cemu_sdl_patches_config "$patch_src" >"${res}/${CEMU_SDL_PATCHES_INLINE_NAME}"
	else
		: >"${res}/${CEMU_SDL_PATCHES_INLINE_NAME}"
	fi
	printf 'launcher %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" >"${res}/${marker_name}"
	echo "  → SDL Mach-O launcher ($name → ${name}.real)"
}

cemu_remove_sdl_launcher() {
	local app="$1"
	cemu_restore_mach_o_launcher "$app" >/dev/null || true
	rm -f "${app}/Contents/Resources/${CEMU_SDL_PATCHES_INLINE_NAME}" \
		"${app}/Contents/Resources/.cemu_sdl_launcher_active"
}
