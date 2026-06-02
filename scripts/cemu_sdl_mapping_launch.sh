#!/usr/bin/env bash
# Wrapper — use launch_cemu.sh (universal launcher).
exec "$(dirname "$0")/launch_cemu.sh" "$@"
