# Security & transparency

This project is **fully open source** (MIT). There is no network access, background daemon, or data collection.

## Why antivirus may flag the installer

| Component | What it is |
|-----------|------------|
| `CemuSDLFix.app` | Bash wrapper that runs `install_cemu_sdl_fix.sh` — modifies your local Cemu `.app` |
| `cemu_sdl_launcher_*` | Small **Mach-O** stubs (~35 KB arm64 / ~10 KB x86_64) copied into Cemu as `CFBundleExecutable` |
| `codesign --sign -` | Ad-hoc re-sign of Cemu after plist/binary changes (required on macOS) |

Heuristics often flag: unsigned binaries, apps that patch other apps, and new Mach-O files without reputation. That does **not** mean malware — you can audit everything below.

## Verify from source (recommended)

```bash
git clone https://github.com/stocktormod-design/cemu-macos-sdl-fix.git
cd cemu-macos-sdl-fix
./scripts/verify_build.sh          # rebuild launchers, print SHA-256
./scripts/build_cemu_sdl_fix_app.sh
```

Compare the printed hashes with [RELEASE_CHECKSUMS.txt](RELEASE_CHECKSUMS.txt) on the GitHub release.

Launcher source (entire native “stub”):

- [`scripts/cemu_sdl_launcher/launcher.c`](scripts/cemu_sdl_launcher/launcher.c) — sets `SDL_GAMECONTROLLERCONFIG*` env vars, `execv()` into `YourCemuBinary.real`

Install logic (no obfuscation):

- [`scripts/install_cemu_sdl_fix.sh`](scripts/install_cemu_sdl_fix.sh)

## What the installer changes on your Mac

Only inside **your** Cemu `.app` bundle(s):

1. `Contents/Resources/cemu_sdl_mappings.txt` — SDL gamecontroller DB lines  
2. `Contents/Resources/cemu_sdl_patches_inline.txt` — device patches  
3. `Contents/MacOS/<CemuBinary>.real` — original Cemu executable (renamed)  
4. `Contents/MacOS/<CemuBinary>` — open-source launcher (replaces main executable)  
5. `Contents/Info.plist` — optional `LSEnvironment` backup  
6. Ad-hoc code signature refresh  

Log file: `~/Library/Application Support/Cemu/sdl_fix_install.log`

## Releases

Each [GitHub Release](https://github.com/stocktormod-design/cemu-macos-sdl-fix/releases) includes:

- **Source code** (zip/tar.gz) — full repository at that tag  
- **CemuSDLFix.zip** — double-click installer (build from the same tag)  
- **RELEASE_CHECKSUMS.txt** — SHA-256 of launcher binaries  

## Report issues

Open a GitHub issue with macOS version, Cemu build, and (if safe) relevant lines from the install log.
