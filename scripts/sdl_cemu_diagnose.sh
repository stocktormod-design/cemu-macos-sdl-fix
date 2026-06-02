#!/usr/bin/env bash
# Diagnose where 8BitDo Ultimate 2C (2DC8:301B) drops out vs Cemu's SDL 2.30.3 path.
set -euo pipefail

CEMU_BIN="/Applications/Cemu_Metal_arm64.app/Contents/MacOS/Cemu_Metal_arm64"
LOG_DIR="${HOME}/Library/Application Support/Cemu"
MAPPING='0300a769c82d00001b30000001000000,8BitDo Ultimate 2C Wireless,a:b0,b:b1,back:b10,dpdown:h0.4,dpleft:h0.8,dpright:h0.2,dpup:h0.1,guide:b12,leftshoulder:b6,leftstick:b13,lefttrigger:a5,leftx:a0,lefty:a1,paddle1:b2,paddle2:b5,rightshoulder:b7,rightstick:b14,righttrigger:a4,rightx:a2,righty:a3,start:b11,x:b3,y:b4,platform:Mac OS X'

echo "=== 1) Cemu paths ==="
echo "Log file: ${LOG_DIR}/log.txt"
echo "Settings: ${LOG_DIR}/settings.xml"
echo "Binary:   ${CEMU_BIN}"
if [[ -f "$CEMU_BIN" ]]; then
  strings "$CEMU_BIN" | grep -m1 "SDL-" || true
  echo -n "Embedded DB has Ultimate 2C (1b30): "
  if strings "$CEMU_BIN" | grep -q "1b30"; then echo "YES"; else echo "NO (expected root cause)"; fi
else
  echo "Cemu Metal binary not found at default path."
fi

echo
echo "=== 2) IOHID / macOS sees device ==="
ioreg -r -c IOHIDDevice 2>/dev/null | grep -i "8BitDo Ultimate 2C" | head -3 || echo "(no match — connect controller via BT)"

echo
echo "=== 3) SDL2 (Homebrew) — joystick vs gamecontroller ==="
if [[ -x /opt/homebrew/bin/brew ]] && [[ -f /opt/homebrew/lib/libSDL2.dylib ]]; then
  cat > /tmp/sdl2_gc_test.c <<'CEOF'
#include <SDL.h>
#include <stdio.h>
int main(void) {
  SDL_Init(SDL_INIT_GAMECONTROLLER | SDL_INIT_JOYSTICK);
  int n = SDL_NumJoysticks();
  printf("NumJoysticks=%d\n", n);
  for (int i = 0; i < n; i++) {
    char guid[33];
    SDL_JoystickGetGUIDString(SDL_JoystickGetDeviceGUID(i), guid, sizeof guid);
  printf("  [%d] %s guid=%s IsGameController=%d\n", i,
      SDL_JoystickNameForIndex(i), guid, (int)SDL_IsGameController(i));
  }
  SDL_Quit();
  return 0;
}
CEOF
  clang -I/opt/homebrew/include/SDL2 -L/opt/homebrew/lib -lSDL2 /tmp/sdl2_gc_test.c -o /tmp/sdl2_gc_test 2>/dev/null && /tmp/sdl2_gc_test
else
  echo "Install: brew install sdl2"
fi

echo
echo "=== 4) SDL3 GAMEPAD-only (mimics Cemu InitSDL) ==="
SDL3_H="$(find /opt/homebrew/Cellar/sdl3 -name SDL.h 2>/dev/null | head -1)"
if [[ -n "$SDL3_H" ]]; then
  INC="$(dirname "$(dirname "$SDL3_H")")"
  cat > /tmp/sdl3_gp_test.c <<'CEOF'
#include <SDL3/SDL.h>
#include <stdio.h>
int main(void) {
  printf("SDL: %s\n", SDL_GetRevision());
  if (!SDL_InitSubSystem(SDL_INIT_GAMEPAD | SDL_INIT_HAPTIC)) {
    fprintf(stderr, "init failed: %s\n", SDL_GetError()); return 1;
  }
  int c = 0; SDL_JoystickID *ids = SDL_GetGamepads(&c);
  printf("SDL_GetGamepads=%d\n", c);
  if (ids) { for (int i=0;i<c;i++)
    printf("  %s\n", SDL_GetGamepadNameForID(ids[i]));
    SDL_free(ids); }
  int j=0; SDL_JoystickID *jids = SDL_GetJoysticks(&j);
  printf("SDL_GetJoysticks=%d\n", j);
  SDL_Quit();
  return 0;
}
CEOF
  clang -I"$INC" -L/opt/homebrew/lib -lSDL3 /tmp/sdl3_gp_test.c -o /tmp/sdl3_gp_test 2>/dev/null && /tmp/sdl3_gp_test
else
  echo "Install: brew install sdl3"
fi

echo
echo "=== 5) Launch Cemu with manual mapping (workaround test) ==="
echo "export SDL_GAMECONTROLLERCONFIG='${MAPPING}'"
echo "open -a Cemu_Metal_arm64"
echo
echo "Enable Cemu Input logging: set <logflag>32</logflag> in settings.xml (bit InputAPI=5 -> 1<<5=32)"
