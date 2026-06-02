#!/usr/bin/env bash
# Build CemuSDLFix.app for distribution (Git / zip). Offline, no network.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="CemuSDLFix.app"
OUT_APP="${REPO_ROOT}/${APP_NAME}"
KIT="${OUT_APP}/Contents/Resources/cemu-sdl-fix"

echo "Building ${OUT_APP} …"

# Prebuilt Mach-O launchers (arm64 + x86_64) required for Dock fix
if [[ ! -x "${REPO_ROOT}/scripts/bin/cemu_sdl_launcher_arm64" ]]; then
	echo "Building launchers …"
	"${REPO_ROOT}/scripts/build_cemu_sdl_launcher.sh"
fi

rm -rf "$OUT_APP"

mkdir -p "${OUT_APP}/Contents/MacOS"
mkdir -p "${KIT}/lib"
mkdir -p "${KIT}/bin"
mkdir -p "${KIT}/data"

cp "${REPO_ROOT}/scripts/install_cemu_sdl_fix.sh" \
	"${REPO_ROOT}/scripts/uninstall_cemu_sdl_fix.sh" \
	"${REPO_ROOT}/scripts/launch_cemu.sh" \
	"${KIT}/"

cp "${REPO_ROOT}/scripts/lib/"*.sh "${KIT}/lib/"
cp "${REPO_ROOT}/scripts/bin/cemu_sdl_launcher_"* "${KIT}/bin/"
cp "${REPO_ROOT}/scripts/data/"* "${KIT}/data/"

cat >"${OUT_APP}/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleDevelopmentRegion</key>
	<string>en</string>
	<key>CFBundleExecutable</key>
	<string>CemuSDLFix</string>
	<key>CFBundleIdentifier</key>
	<string>no.holand.cemu-sdl-fix</string>
	<key>CFBundleName</key>
	<string>Cemu SDL Fix</string>
	<key>CFBundlePackageType</key>
	<string>APPL</string>
	<key>CFBundleShortVersionString</key>
	<string>1.1.0</string>
	<key>CFBundleVersion</key>
	<string>3</string>
	<key>LSMinimumSystemVersion</key>
	<string>13.0</string>
	<key>NSHighResolutionCapable</key>
	<true/>
</dict>
</plist>
PLIST

cat >"${OUT_APP}/Contents/MacOS/CemuSDLFix" <<'LAUNCHER'
#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../Resources/cemu-sdl-fix" && pwd)"
export CEMU_SDL_FIX_ROOT="$ROOT"
LOG="${HOME}/Library/Application Support/Cemu/sdl_fix_install.log"
mkdir -p "$(dirname "$LOG")"

{
  echo "==== $(date) ===="
  "${ROOT}/install_cemu_sdl_fix.sh" --list
  echo "---"
  "${ROOT}/install_cemu_sdl_fix.sh" --force --all
} >>"$LOG" 2>&1

LIST=$("${ROOT}/install_cemu_sdl_fix.sh" --list 2>/dev/null | tail -n +2 || true)

/usr/bin/osascript <<APPLESCRIPT
set msg to "SDL gamepad fix installed.

You are done — launch Cemu from the Dock and check Input → SDLController.

Full source & security info:
https://github.com/stocktormod-design/cemu-macos-sdl-fix

Log: ${LOG}

${LIST}"
display dialog msg buttons {"OK"} default button "OK" with title "Cemu SDL Fix"
APPLESCRIPT
LAUNCHER

chmod +x "${OUT_APP}/Contents/MacOS/CemuSDLFix"
chmod +x "${KIT}/install_cemu_sdl_fix.sh" "${KIT}/uninstall_cemu_sdl_fix.sh" "${KIT}/launch_cemu.sh"
chmod +x "${KIT}/bin/"*

echo "Done: ${OUT_APP}"
echo "Zip for Git:  cd \"$(dirname "$OUT_APP")\" && zip -r CemuSDLFix.zip \"$(basename "$OUT_APP")\""
