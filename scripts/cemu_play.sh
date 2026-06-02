#!/bin/bash
# Play session: light DSU bridge only while you play. No .app. Stops on Enter.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BRIDGE="$ROOT/archive/dsu_bridge_experiment/8bitdo_dsu_bridge.py"
CEMU_APP="${CEMU_APP:-/Applications/Cemu_Metal_arm64.app}"
PROFILES="$HOME/Library/Application Support/Cemu/controllerProfiles"
SLOT="${SLOT:-2}"
FPS="${FPS:-20}"
PORT="${PORT:-26760}"

cleanup() {
  if [[ -n "${BRIDGE_PID:-}" ]] && kill -0 "$BRIDGE_PID" 2>/dev/null; then
    kill "$BRIDGE_PID" 2>/dev/null || true
    wait "$BRIDGE_PID" 2>/dev/null || true
  fi
  "$ROOT/scripts/stop_bridge.sh" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo "=== Cemu + 8BitDo (DSU session) ==="
echo "Steam Input / Enjoyable / SDL often fail on Mac with Ultimate 2C BT."
echo "This uses a minimal bridge only while this terminal is open."
echo ""

"$ROOT/scripts/stop_bridge.sh"

# Point GamePad profile at DSU (keeps your mappings in 8bitdo_dsu_auto.xml)
mkdir -p "$PROFILES"
cat > "$PROFILES/controller0.xml" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<emulated_controller>
	<type>Wii U GamePad</type>
	<profile>8bitdo_dsu_auto</profile>
	<toggle_display>0</toggle_display>
</emulated_controller>
EOF

echo "Starting bridge (--light, ${FPS} FPS)..."
python3 -u "$BRIDGE" \
  --slot "$SLOT" \
  --port "$PORT" \
  --fps "$FPS" \
  --profile 8bitdo \
  --light \
  --gyro-source off \
  >/tmp/8bitdo_bridge_session.log 2>&1 &
BRIDGE_PID=$!
sleep 1.5

if ! kill -0 "$BRIDGE_PID" 2>/dev/null; then
  echo "Bridge failed:"
  tail -30 /tmp/8bitdo_bridge_session.log
  exit 1
fi

if grep -q "Using controller" /tmp/8bitdo_bridge_session.log; then
  grep "Using controller" /tmp/8bitdo_bridge_session.log | tail -1
else
  echo "WARNING: controller not detected yet — check BT, run: python3 $ROOT/scripts/test_controller.py"
fi

echo ""
echo "Cemu settings:"
echo "  API: DSUController"
echo "  Controller: Controller ${SLOT}"
echo "  Server: 127.0.0.1:${PORT}"
echo "  Profile: 8bitdo_dsu_auto"
echo ""
echo "If no input: open Cemu Input, pick Controller ${SLOT} again once."
echo ""

if [[ -d "$CEMU_APP" ]]; then
  open -a "$CEMU_APP"
else
  echo "Start Cemu manually (app not at $CEMU_APP)"
fi

echo "Playing... Press ENTER here when done (stops bridge, saves battery)."
read -r
