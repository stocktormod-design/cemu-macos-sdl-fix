#!/usr/bin/env bash
# Build release artifacts and write RELEASE_CHECKSUMS.txt (run before tagging).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="${1:-}"
[[ -n "$VERSION" ]] || { echo "Usage: $0 <version>   e.g. 1.1.0" >&2; exit 1; }

./scripts/verify_build.sh
./scripts/build_cemu_sdl_fix_app.sh
rm -f CemuSDLFix.zip
zip -r CemuSDLFix.zip CemuSDLFix.app -x "*.DS_Store" >/dev/null

{
	echo "# SHA-256 checksums for cemu-macos-sdl-fix v${VERSION}"
	echo "# Verify: ./scripts/verify_build.sh"
	echo ""
	if command -v shasum >/dev/null 2>&1; then
		shasum -a 256 scripts/bin/cemu_sdl_launcher_arm64 scripts/bin/cemu_sdl_launcher_x86_64 CemuSDLFix.zip
	else
		sha256sum scripts/bin/cemu_sdl_launcher_arm64 scripts/bin/cemu_sdl_launcher_x86_64 CemuSDLFix.zip
	fi
} >RELEASE_CHECKSUMS.txt

echo ""
echo "Wrote RELEASE_CHECKSUMS.txt"
echo "Next:"
echo "  git add -A && git commit -m \"Release v${VERSION}\""
echo "  git tag v${VERSION} && git push origin main --tags"
echo "  gh release create v${VERSION} CemuSDLFix.zip RELEASE_CHECKSUMS.txt --notes-file RELEASE_NOTES.md"
