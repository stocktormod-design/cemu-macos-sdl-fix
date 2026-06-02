#!/usr/bin/env python3
"""Quick check: does Mac see 8BitDo with analog sticks?"""
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_JOYSTICK_HIDAPI", "1")

try:
    import pygame
except ImportError:
    print("Install pygame: python3 -m pip install --user pygame")
    sys.exit(1)

pygame.init()
pygame.joystick.init()
n = pygame.joystick.get_count()
print(f"Controllers found: {n}")
if n < 1:
    print("No controller. Connect BT or dongle+adapter, then retry.")
    sys.exit(1)

j = pygame.joystick.Joystick(0)
j.init()
print(f"Name: {j.get_name()}")
print(f"Axes: {j.get_numaxes()}  Buttons: {j.get_numbuttons()}")
print("Move LEFT stick ~3 sec...")
for _ in range(90):
    pygame.event.pump()
    if j.get_numaxes() >= 2:
        x, y = j.get_axis(0), j.get_axis(1)
        print(f"  stick: x={x:+.2f} y={y:+.2f}")
    time.sleep(0.033)
pygame.joystick.quit()
pygame.quit()
print("OK — analog values changing means Mac + pygame see your pad.")
