# 8BitDo -> Cemu DSU Bridge (macOS)

This bridge exposes your first detected controller as a DSU/Cemuhook source for Cemu.

## 1) Install dependency

```bash
python3 -m pip install --user pygame
```

## 2) Run the bridge

From this folder:

```bash
python3 8bitdo_dsu_bridge.py --slot 2
```

You should see:

- `Using controller: ...`
- `DSU server listening on 127.0.0.1:26760`
- `Slot mode: fixed (DSU2)`

Keep this terminal open while playing.

### Slot option

- `--slot 1|2|3|4`: send only to that Cemu controller slot
- `--slot 0`: auto mode (broadcast to DSU1-DSU4)
- `--fps 30|60|90|120`: lower value uses less CPU/battery
- `--verbose`: print detailed subscribe/live stats

Example:

```bash
python3 8bitdo_dsu_bridge.py --slot 3 --fps 30 --verbose
```

## Optional UI launcher

If you do not want terminal usage, run:

```bash
python3 8bitdo_dsu_bridge_ui.py
```

Then choose slot and press `Start`.

## Build a native `.app` (double-click)

From the same folder:

```bash
python3 -m pip install --user py2app
python3 setup_bridge_app.py py2app
```

App output:

- `dist/8bitdo_dsu_bridge_ui.app`

You can move/rename it in Finder after build.

## 3) Configure Cemu

In Cemu:

- `Options` -> `GamePad motion source`
- Select the same slot you configured (`DSU1`..`DSU4`)
- Enable `Also use for buttons/axes`

Your `settings.xml` already has DSU host set to `127.0.0.1:26760`.

## Notes

- This v1 bridge sends buttons/sticks/triggers and basic static motion values.
- It maps controller 0 from pygame (first detected controller).
- If no controller is found, reconnect controller before launching script.
