# Cemu SDL Controller Fix (macOS)

Fix empty **SDLController** list in [Cemu](https://cemu.info/) on Mac when the system sees your gamepad (e.g. **8BitDo Ultimate 2C** over Bluetooth) but Cemu’s bundled SDL 2.30.3 has no mapping for it.

**One-time install → launch Cemu from Dock as usual.** No terminal, no DSU bridge, no Steam Input.

## Quick start

### Option A — Double-click installer (easiest)

1. Download **CemuSDLFix.zip** from [Releases](https://github.com/stocktormod-design/cemu-macos-sdl-fix/releases) (or build below).
2. Unzip and open **`CemuSDLFix.app`**.
3. Connect your controller → open Cemu → **Input → SDLController**.

### Option B — Terminal

```bash
git clone https://github.com/stocktormod-design/cemu-macos-sdl-fix.git
cd cemu-macos-sdl-fix
chmod +x scripts/*.sh scripts/lib/*.sh
./scripts/install_cemu_sdl_fix.sh --force
```

Uninstall: `./scripts/uninstall_cemu_sdl_fix.sh`

## Build the installer app (maintainers)

```bash
./scripts/build_cemu_sdl_launcher.sh   # if bin/ is missing
./scripts/build_cemu_sdl_fix_app.sh
zip -r CemuSDLFix.zip CemuSDLFix.app
```

## How it works

| Problem | Fix |
|--------|-----|
| Cemu only lists SDL **gamepads** | Add missing **GUID → button mapping** for your device |
| `Info.plist` env ignored on recent macOS | Tiny **Mach-O launcher** sets `SDL_GAMECONTROLLERCONFIG` then `exec`s the real Cemu binary (`*.real`) |

**Performance:** launcher runs once at startup (~50 KB stub); zero overhead while playing.

Details: [CEMU_SDL_FIX.md](CEMU_SDL_FIX.md)

## Requirements

- macOS 13+
- Cemu (Metal and/or vanilla `.app`)
- Writable Cemu.app bundle (Applications or user folder)

## Custom mappings

Add lines to `~/Library/Application Support/Cemu/gamecontroller_user.txt`, then re-run install with `--force`.

## License

MIT — see [LICENSE](LICENSE). Not affiliated with Cemu or 8BitDo.
