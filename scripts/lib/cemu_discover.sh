# Shared Cemu.app discovery (source from other scripts).

cemu_app_has_binary() {
	local app="$1"
	local macos="${app}/Contents/MacOS"
	local name
	for name in Cemu_Metal_arm64 Cemu; do
		[[ -f "${macos}/${name}" || -f "${macos}/${name}.real" ]] && return 0
	done
	return 1
}

cemu_find_launcher_name() {
	local app="$1"
	local macos="${app}/Contents/MacOS"
	local name
	for name in Cemu_Metal_arm64 Cemu; do
		if [[ -f "${macos}/${name}" || -f "${macos}/${name}.real" ]]; then
			printf '%s\n' "$name"
			return 0
		fi
	done
	return 1
}

cemu_app_to_binary() {
	local app="$1"
	local macos="${app}/Contents/MacOS"
	local name
	name="$(cemu_find_launcher_name "$app")" || return 1
	# Prefer real Mach-O binary (not old bash wrapper)
	if [[ -f "${macos}/${name}.real" ]] && ! [[ -x "${macos}/${name}" && "$(file -b "${macos}/${name}" 2>/dev/null)" == *"Mach-O"* ]]; then
		printf '%s\n' "${macos}/${name}.real"
	else
		[[ -f "${macos}/${name}" ]] && printf '%s\n' "${macos}/${name}"
	fi
}

cemu_is_patched() {
	# shellcheck source=cemu_plist.sh
	source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cemu_plist.sh"
	cemu_is_patched_v2 "$1"
}

cemu_can_patch() {
	[[ -w "$1/Contents/MacOS" && -w "$1/Contents/Resources" && -w "$1/Contents/Info.plist" ]] 2>/dev/null
}

cemu_restore_mach_o_launcher() {
	local app="$1"
	local macos="${app}/Contents/MacOS"
	local name exe real

	for name in Cemu_Metal_arm64 Cemu; do
		exe="${macos}/${name}"
		real="${macos}/${name}.real"
		if [[ ! -f "$real" ]]; then
			continue
		fi
		rm -f "$exe"
		mv "$real" "$exe"
		chmod +x "$exe"
		echo "$name"
		return 0
	done
	return 1
}

cemu_discover_apps() {
	local -a found=() unique=()
	local app base

	if [[ -n "${1:-}" ]]; then
		app="$1"
		[[ "$app" == *.app ]] || app="${app%/}.app"
		cemu_app_has_binary "$app" && printf '%s\n' "$app"
		return 0
	fi

	if [[ -n "${CEMU_APP:-}" ]]; then
		app="$CEMU_APP"
		[[ "$app" == *.app ]] || app="${app%/}.app"
		cemu_app_has_binary "$app" && printf '%s\n' "$app"
		return 0
	fi

	while IFS= read -r app; do
		[[ -n "$app" ]] && found+=("$app")
	done < <(mdfind 'kMDItemCFBundleIdentifier == "info.cemu.Cemu"' 2>/dev/null || true)

	for base in \
		"/Applications" \
		"${HOME}/Applications" \
		"${HOME}/Desktop" \
		"${HOME}/Downloads" \
		"${HOME}/Games" \
		; do
		[[ -d "$base" ]] || continue
		while IFS= read -r app; do
			found+=("$app")
		done < <(find "$base" -maxdepth 5 -type d -name '*.app' \( -iname 'Cemu*.app' -o -iname '*cemu*.app' \) 2>/dev/null || true)
	done

	local a u seen=0
	for a in ${found[@]+"${found[@]}"}; do
		cemu_app_has_binary "$a" || continue
		cemu_can_patch "$a" || continue
		seen=0
		for u in ${unique[@]+"${unique[@]}"}; do
			[[ "$u" == "$a" ]] && seen=1 && break
		done
		[[ $seen -eq 0 ]] && unique+=("$a")
	done

	local -a ordered=() metal=() other=()
	for a in "${unique[@]}"; do
		if [[ "$(basename "$a")" == *[Mm]etal* ]]; then
			metal+=("$a")
		else
			other+=("$a")
		fi
	done
	IFS=$'\n'
	metal=($(printf '%s\n' "${metal[@]}" | sort))
	other=($(printf '%s\n' "${other[@]}" | sort))
	unset IFS
	ordered=("${metal[@]}" "${other[@]}")

	[[ ${#ordered[@]} -gt 0 ]] && printf '%s\n' "${ordered[@]}"
	return 0
}
