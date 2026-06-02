#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${ROOT}/scripts/cemu_sdl_launcher/launcher.c"
OUT="${ROOT}/scripts/bin"
mkdir -p "$OUT"

CFLAGS=(-O2 -Wall -Wextra)

echo "Building arm64 launcher …"
clang "${CFLAGS[@]}" -arch arm64 -o "${OUT}/cemu_sdl_launcher_arm64" "$SRC"

echo "Building x86_64 launcher …"
clang "${CFLAGS[@]}" -arch x86_64 -o "${OUT}/cemu_sdl_launcher_x86_64" "$SRC"

echo "OK:"
file "${OUT}/cemu_sdl_launcher_arm64" "${OUT}/cemu_sdl_launcher_x86_64"
