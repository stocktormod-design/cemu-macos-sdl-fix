# Cemu SDL Fix (macOS)

Fixes empty **SDLController** list in Cemu when macOS / Steam / browsers see your pad, but Cemu’s bundled SDL 2.30.3 has no mapping (e.g. **8BitDo Ultimate 2C** over Bluetooth).

## Plug and play (share with friends)

1. Download or clone this repo.
2. **Double-click `CemuSDLFix.app`** (build it once below if missing).
3. Connect the controller → start **Cemu from Dock** → **Input → SDLController**.

No terminal, no Steam Input, no DSU bridge.

### Build the installer app (maintainers)

```bash
./scripts/build_cemu_sdl_fix_app.sh
zip -r CemuSDLFix.zip CemuSDLFix.app   # upload this
```

### Terminal-only install

```bash
chmod +x scripts/*.sh scripts/lib/*.sh
./scripts/install_cemu_sdl_fix.sh --force
```

Uninstall: `./scripts/uninstall_cemu_sdl_fix.sh`

## What the fix actually does

| Problem | Cause |
|--------|--------|
| Cemu shows **no controllers** | Cemu only lists **gamepads** (`SDL_GetGamepads`), not raw joysticks |
| Your pad is invisible | Bundled SDL DB is missing your device’s **GUID mapping** |
| Dock launch failed earlier | `Info.plist` env alone is unreliable on recent macOS |

| Solution | How |
|----------|-----|
| **Mapping database** | Merged `gamecontrollerdb.txt` + patches (Ultimate 2C Mac/Win/Linux GUIDs) into the app |
| **SDL env at startup** | Tiny **Mach-O launcher** (~50 KB) replaces `Cemu` / `Cemu_Metal_arm64`; sets `SDL_GAMECONTROLLERCONFIG` + `SDL_GAMECONTROLLERCONFIG_FILE`, then `exec`s `*.real` (real Cemu binary) |
| **Codesign** | Ad-hoc re-sign after patching so macOS still opens the app |

Nothing runs in the background. No network. No Cemu source rebuild.

## Performance

**Effectively zero** in-game:

- Launcher runs once at app start, `exec` into Cemu — no extra process while playing.
- ~50 KB stub; no polling, no bridge, no CPU loop.
- SDL mapping lookup is the same cost Cemu already pays; you only added entries to the DB.
- Real game binary is unchanged (`Cemu_Metal_arm64.real` / `Cemu.real`).

## Metal vs vanilla Cemu

Separate apps — installer patches **all** `*Cemu*.app` it finds (Applications, Desktop, etc.). Use the same icon you installed into.

## Custom mappings

Append lines to:

`~/Library/Application Support/Cemu/gamecontroller_user.txt`

Then re-run install with `--force`.

## Files

| Path | Role |
|------|------|
| `scripts/install_cemu_sdl_fix.sh` | One-time patch |
| `scripts/bin/cemu_sdl_launcher_*` | Prebuilt Dock launchers |
| `scripts/data/gamecontroller_patches.txt` | Device patches |
| `CemuSDLFix.app` | Double-click installer |
