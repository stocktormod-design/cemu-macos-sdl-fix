#!/bin/bash
# Stop any leftover DSU bridge / Python processes from the old setup.
pkill -f "8bitdo_dsu_bridge.py" 2>/dev/null || true
pkill -f "8BitDo DSU Bridge" 2>/dev/null || true
rm -f /tmp/8bitdo_dsu_bridge.pid 2>/dev/null || true
echo "Bridge cleanup done."
