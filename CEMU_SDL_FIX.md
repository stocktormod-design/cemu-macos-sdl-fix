# Cemu SDL Fix (macOS) — technical overview

## Problem

| Layer | What you see |
|-------|----------------|
| macOS | Controller works in System Settings / Game Controllers |
| Cemu → SDLController | **Empty list** |
| Cause | Cemu’s SDL build has **no gamecontroller mapping** for your device’s GUID |

Cemu does **not** list all joysticks. It uses SDL’s **gamepad** API (`SDL_GetGamepads` on SDL 2.30.x / gamepad subsystem). SDL only exposes a device as a gamepad when a line exists in the gamecontroller database:

```text
<GUID>,<name>,a:b0,b:b1,...,platform:Mac OS X
```

Cemu ships a **frozen** copy of that database inside the app. New controllers (Ultimate 2C BT, etc.) ship after that DB was cut — so they stay “joystick only” and Cemu ignores them.

## Why the fix works

1. **Merge** a larger mapping file (Cemu’s DB + community entries + patches).
2. **Inject** it via standard SDL environment variables **before** Cemu starts:
   - `SDL_GAMECONTROLLERCONFIG_FILE` → path to full merged file
   - `SDL_GAMECONTROLLERCONFIG` → high-priority inline lines (device patches)
3. **Ensure injection on Dock launch** with a Mach-O launcher as `CFBundleExecutable` that `setenv` + `exec` the real binary (`*.real`).

SDL then classifies your pad as a gamecontroller; Cemu’s existing SDL input path works unchanged.

No Cemu recompile. No runtime hook. No network.

## Device support

### Not limited to 8BitDo Ultimate 2C

Ultimate 2C is the **original tested device**; the fix is **generic SDL mapping injection**.

| Source | Contents |
|--------|----------|
| `scripts/data/gamecontrollerdb.txt` | ~190 mappings (8BitDo, HORI, ASUS ROG, PlayStation-style, Xbox-style, …) |
| `scripts/data/gamecontroller_patches.txt` | Devices **missing from Cemu’s embedded DB** (Ultimate 2C Mac/Win/Linux GUIDs, etc.) |
| `~/Library/Application Support/Cemu/gamecontroller_user.txt` | Per-user additions (merged on install) |

### Will work

- Controller visible in macOS.
- A mapping exists for **your GUID** + connection (USB/BT can differ).
- You use Cemu’s **SDL controller** input (not only DSU).

### Might not work

- macOS does not see the device.
- GUID not in any DB and you have not added a mapping.
- Pad needs non-SDL software (some mobile/X-input modes).
- Wrong Cemu app binary (Metal vs vanilla) without running install on that `.app`.

### Find your GUID (macOS)

```bash
./scripts/sdl_cemu_diagnose.sh
```

Or with Homebrew SDL2: init joystick subsystem, print `SDL_JoystickGetGUIDString` and `SDL_IsGameController`.

## Install artifacts (per Cemu.app)

| Path | Role |
|------|------|
| `Contents/MacOS/<Binary>` | Open-source launcher |
| `Contents/MacOS/<Binary>.real` | Original Cemu executable |
| `Contents/Resources/cemu_sdl_mappings.txt` | Merged DB |
| `Contents/Resources/cemu_sdl_patches_inline.txt` | Inline patch lines for launcher |

## Security / source transparency

See [SECURITY.md](SECURITY.md).

## Quick commands

```bash
./scripts/install_cemu_sdl_fix.sh --force   # install / refresh
./scripts/uninstall_cemu_sdl_fix.sh         # remove patch
./scripts/verify_build.sh                   # rebuild launcher, print SHA-256
```
