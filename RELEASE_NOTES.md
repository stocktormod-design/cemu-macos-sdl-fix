## Install

1. Download **CemuSDLFix.zip** from this release (or use **Source code** to build yourself).
2. Unzip and double-click **CemuSDLFix.app**.
3. Launch Cemu from Dock → **Input → SDLController**.

## Transparency / antivirus

- Full source is attached as **Source code (zip)** and on the `main` branch.
- Native launcher source: `scripts/cemu_sdl_launcher/launcher.c` (~120 lines, `setenv` + `execv` only).
- Verify binaries: `./scripts/verify_build.sh` and compare with **RELEASE_CHECKSUMS.txt**.
- See [SECURITY.md](https://github.com/stocktormod-design/cemu-macos-sdl-fix/blob/main/SECURITY.md).

No network, no background process, no telemetry.
