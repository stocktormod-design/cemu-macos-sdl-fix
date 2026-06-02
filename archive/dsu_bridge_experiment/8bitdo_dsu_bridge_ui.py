#!/usr/bin/env python3
import atexit
import importlib.util
import io
import os
import pathlib
import queue
import signal
import subprocess
import sys
import threading
import time
import socket
import tkinter as tk
import xml.etree.ElementTree as ET
from tkinter import messagebox

try:
    import pygame
except Exception:
    pygame = None

ROOT = pathlib.Path(__file__).resolve().parent
BRIDGE = ROOT / "8bitdo_dsu_bridge.py"
LOG_FILE = pathlib.Path("/tmp/8bitdo_bridge_v7.log")

CEMU_PROFILES_DIR = pathlib.Path.home() / "Library" / "Application Support" / "Cemu" / "controllerProfiles"
CEMU_CONTROLLER0 = CEMU_PROFILES_DIR / "controller0.xml"
MANAGED_PROFILE_NAME = "8bitdo_dsu_auto"
MANAGED_PROFILE_PATH = CEMU_PROFILES_DIR / f"{MANAGED_PROFILE_NAME}.xml"
BRIDGE_PID_FILE = pathlib.Path("/tmp/8bitdo_dsu_bridge.pid")


class QueueLogWriter(io.TextIOBase):
    def __init__(self, log_queue: queue.Queue[str]) -> None:
        self.log_queue = log_queue
        self._buf = ""

    def write(self, text: str) -> int:
        if not text:
            return 0
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self.log_queue.put(line.rstrip())
        return len(text)

    def flush(self) -> None:
        if self._buf.strip():
            self.log_queue.put(self._buf.strip())
            self._buf = ""


def bridge_script_path() -> pathlib.Path:
    resource = os.environ.get("RESOURCEPATH")
    if resource:
        candidate = pathlib.Path(resource) / "8bitdo_dsu_bridge.py"
        if candidate.exists():
            return candidate
    return BRIDGE


def load_dsu_bridge_class():
    path = bridge_script_path()
    spec = importlib.util.spec_from_file_location("dsu_bridge", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load bridge module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DsuBridge


class BridgeUI:
    def __init__(self) -> None:
        self.bridge = None
        self.bridge_thread = None
        self.log_queue: queue.Queue[str] = queue.Queue()

        self.root = tk.Tk()
        self.root.title("8BitDo DSU Bridge v7")
        self.root.geometry("1060x720")
        self.root.minsize(900, 600)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.slot_var = tk.StringVar(value="2")
        self.fps_var = tk.StringVar(value="30")
        self.port_var = tk.StringVar(value="26760")
        self.profile_var = tk.StringVar(value="8bitdo")
        self.l3_var = tk.StringVar(value="13,9,11")
        self.r3_var = tk.StringVar(value="14,10,12")
        self.lx_axis_var = tk.StringVar(value="0")
        self.ly_axis_var = tk.StringVar(value="1")
        self.rx_axis_var = tk.StringVar(value="2")
        self.ry_axis_var = tk.StringVar(value="3")
        self.verbose_var = tk.BooleanVar(value=False)
        self.live_log_var = tk.BooleanVar(value=False)
        self.gyro_emulation_var = tk.BooleanVar(value=True)
        self.gyro_strength_var = tk.StringVar(value="2.4")
        self.auto_apply_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Stopped")

        self._build_ui()
        self.nuke_logs()
        self.log_line("[ui] v7 initialized")
        self.log_line("[ui] Tip: disable Verbose logs for lower battery usage")
        self.log_line(f"[ui] logfile: {LOG_FILE}")
        atexit.register(self._stop_bridge_process)
        self.root.after(300, self.drain)

    def _build_ui(self) -> None:
        top = tk.Frame(self.root, padx=12, pady=10)
        top.pack(fill="x")
        tk.Label(top, text="8BitDo -> Cemu Bridge", font=("Helvetica", 15, "bold")).pack(side="left")
        tk.Label(top, textvariable=self.status_var, font=("Helvetica", 12)).pack(side="right")

        row = tk.Frame(self.root, padx=12, pady=6)
        row.pack(fill="x")

        tk.Label(row, text="Slot").grid(row=0, column=0, sticky="w")
        tk.OptionMenu(row, self.slot_var, "1", "2", "3", "4", "Auto").grid(row=0, column=1, padx=6, sticky="w")

        tk.Label(row, text="FPS").grid(row=0, column=2, sticky="w")
        tk.OptionMenu(row, self.fps_var, "15", "20", "30", "45", "60").grid(row=0, column=3, padx=6, sticky="w")

        tk.Label(row, text="Port").grid(row=0, column=4, sticky="w")
        tk.Entry(row, textvariable=self.port_var, width=8).grid(row=0, column=5, padx=6, sticky="w")

        tk.Label(row, text="Profile").grid(row=0, column=6, sticky="w")
        tk.OptionMenu(row, self.profile_var, "8bitdo", "standard").grid(row=0, column=7, padx=6, sticky="w")

        tk.Label(row, text="L3 idx").grid(row=1, column=0, sticky="w", pady=8)
        tk.Entry(row, textvariable=self.l3_var, width=16).grid(row=1, column=1, padx=6, sticky="w")
        tk.Button(row, text="Detect L3", command=self.detect_l3, width=10).grid(row=1, column=2, padx=(0, 10), sticky="w")
        tk.Label(row, text="R3 idx").grid(row=1, column=3, sticky="w", pady=8)
        tk.Entry(row, textvariable=self.r3_var, width=16).grid(row=1, column=4, padx=6, sticky="w")
        tk.Button(row, text="Detect R3", command=self.detect_r3, width=10).grid(row=1, column=5, padx=(0, 10), sticky="w")

        tk.Label(row, text="LX").grid(row=2, column=0, sticky="w", pady=8)
        tk.Entry(row, textvariable=self.lx_axis_var, width=4).grid(row=2, column=1, padx=6, sticky="w")
        tk.Label(row, text="LY").grid(row=2, column=2, sticky="w", pady=8)
        tk.Entry(row, textvariable=self.ly_axis_var, width=4).grid(row=2, column=3, padx=6, sticky="w")
        tk.Label(row, text="RX").grid(row=2, column=4, sticky="w", pady=8)
        tk.Entry(row, textvariable=self.rx_axis_var, width=4).grid(row=2, column=5, padx=6, sticky="w")
        tk.Label(row, text="RY").grid(row=2, column=6, sticky="w", pady=8)
        tk.Entry(row, textvariable=self.ry_axis_var, width=4).grid(row=2, column=7, padx=6, sticky="w")

        tk.Checkbutton(row, text="Auto-apply Cemu profile", variable=self.auto_apply_var).grid(row=3, column=0, columnspan=4, sticky="w", pady=8)
        tk.Checkbutton(row, text="Verbose logs", variable=self.verbose_var).grid(row=3, column=4, columnspan=3, sticky="w", pady=8)
        tk.Checkbutton(row, text="Live log in UI (more CPU)", variable=self.live_log_var).grid(row=4, column=0, columnspan=4, sticky="w", pady=2)
        tk.Checkbutton(row, text="Gyro emulation (R-stick)", variable=self.gyro_emulation_var).grid(row=4, column=4, columnspan=3, sticky="w", pady=2)
        tk.Label(row, text="Gyro strength").grid(row=4, column=7, sticky="w", pady=2)
        tk.Entry(row, textvariable=self.gyro_strength_var, width=6).grid(row=4, column=8, padx=6, sticky="w")

        btns = tk.Frame(self.root, padx=12, pady=8)
        btns.pack(fill="x")
        self.start_btn = tk.Button(btns, text="Start", width=12, command=self.start)
        self.start_btn.pack(side="left")
        self.stop_btn = tk.Button(btns, text="Stop", width=12, state="disabled", command=self.stop)
        self.stop_btn.pack(side="left", padx=8)
        tk.Button(btns, text="Apply Cemu", width=12, command=self.apply_cemu).pack(side="left", padx=8)
        tk.Button(btns, text="Nuke Logs", width=12, command=self.nuke_logs).pack(side="left", padx=8)
        tk.Button(btns, text="Open Log File", width=12, command=self.open_log_file).pack(side="left", padx=8)

        hint = tk.Label(self.root, text="If this area below is empty, wrong app is open. Must say v7 in title bar.", fg="#aa0000")
        hint.pack(anchor="w", padx=12)

        log_wrap = tk.Frame(self.root, bd=2, relief="sunken")
        log_wrap.pack(fill="both", expand=True, padx=12, pady=10)

        self.log_text = tk.Text(
            log_wrap,
            wrap="word",
            bg="#0a0a0a",
            fg="#79ff79",
            insertbackground="#79ff79",
            font=("Menlo", 12),
            padx=10,
            pady=10,
            borderwidth=0,
        )
        self.log_text.pack(side="left", fill="both", expand=True)
        self.log_text.bind("<Key>", lambda e: "break")

        sb = tk.Scrollbar(log_wrap, orient="vertical", command=self.log_text.yview)
        sb.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=sb.set)


    def _detect_button(self, target_var: tk.StringVar, label: str) -> None:
        if self.proc is not None:
            self.log_line(f"Stop bridge before detecting {label}")
            return
        if pygame is None:
            self.log_line("pygame not available in UI runtime")
            return

        try:
            pygame.init()
            pygame.joystick.init()
            if pygame.joystick.get_count() < 1:
                self.log_line("No controller found for detect")
                return

            joy = pygame.joystick.Joystick(0)
            joy.init()
            self.log_line(f"Detect {label}: press stick click now (5s timeout)")
            deadline = time.time() + 5.0

            while time.time() < deadline:
                pygame.event.pump()
                for i in range(joy.get_numbuttons()):
                    if joy.get_button(i):
                        target_var.set(str(i))
                        self.log_line(f"Detected {label} idx = {i}")
                        return
                time.sleep(0.02)

            self.log_line(f"Detect {label} timed out")
        except Exception as exc:
            self.log_line(f"Detect {label} failed: {exc}")
        finally:
            try:
                pygame.quit()
            except Exception:
                pass

    def detect_l3(self) -> None:
        self._detect_button(self.l3_var, "L3")

    def detect_r3(self) -> None:
        self._detect_button(self.r3_var, "R3")

    def _append_to_widget(self, line: str) -> None:
        if not self.live_log_var.get():
            return
        self.log_text.insert("end", line + "\n")
        # Keep widget bounded so rendering cost does not explode over time.
        try:
            total = int(float(self.log_text.index("end-1c").split(".")[0]))
            if total > 500:
                self.log_text.delete("1.0", f"{total-450}.0")
        except Exception:
            pass
        self.log_text.see("end")

    def _append_to_file(self, line: str) -> None:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def log_line(self, text: str) -> None:
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {text}"
        self._append_to_widget(line)
        self._append_to_file(line)

    def nuke_logs(self) -> None:
        self.log_text.delete("1.0", "end")
        try:
            LOG_FILE.write_text("", encoding="utf-8")
        except Exception:
            pass
        self.log_line("[ui] logs nuked")

    def open_log_file(self) -> None:
        try:
            subprocess.run(["/usr/bin/open", str(LOG_FILE)], check=False)
        except Exception as exc:
            self.log_line(f"open log failed: {exc}")

    def selected_slot(self) -> str:
        return "0" if self.slot_var.get() == "Auto" else self.slot_var.get()


    def _selected_port(self) -> int:
        try:
            p = int(self.port_var.get().strip())
            if 1 <= p <= 65535:
                return p
        except Exception:
            pass
        return 26760

    def _find_available_port(self, start_port: int, attempts: int = 8) -> int:
        for p in range(start_port, start_port + attempts):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                pass
            finally:
                s.close()
        return start_port

    def kill_stale(self) -> None:
        try:
            if BRIDGE_PID_FILE.exists():
                old_pid = int(BRIDGE_PID_FILE.read_text(encoding="utf-8").strip())
                if old_pid != os.getpid():
                    try:
                        os.kill(old_pid, signal.SIGTERM)
                    except OSError:
                        pass
                    time.sleep(0.2)
                    try:
                        os.kill(old_pid, signal.SIGKILL)
                    except OSError:
                        pass
                BRIDGE_PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass

        for cmd in (
            ["/usr/bin/pkill", "-f", "8bitdo_dsu_bridge.py"],
            ["/usr/bin/pkill", "-f", "Contents/Resources/8bitdo_dsu_bridge.py"],
        ):
            try:
                subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as exc:
                self.log_line(f"cleanup warning: {exc}")

        # Give processes a moment to exit after SIGTERM.
        time.sleep(0.25)

        try:
            out = subprocess.check_output(["/usr/sbin/lsof", "-nP", f"-iUDP:{self._selected_port()}", "-t"], text=True)
            pids = [int(x.strip()) for x in out.splitlines() if x.strip()]
            for pid in pids:
                if pid == os.getpid():
                    continue
                try:
                    os.kill(pid, signal.SIGTERM)
                    self.log_line(f"sent SIGTERM to UDP {self._selected_port()} pid {pid}")
                except Exception:
                    pass

            # Re-check and force kill survivors.
            time.sleep(0.25)
            try:
                out2 = subprocess.check_output(["/usr/sbin/lsof", "-nP", f"-iUDP:{self._selected_port()}", "-t"], text=True)
                for line in out2.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    pid = int(line)
                    if pid == os.getpid():
                        continue
                    try:
                        os.kill(pid, signal.SIGKILL)
                        self.log_line(f"sent SIGKILL to UDP {self._selected_port()} pid {pid}")
                    except Exception:
                        pass
            except subprocess.CalledProcessError:
                pass

            time.sleep(0.35)

        except subprocess.CalledProcessError:
            pass
        except Exception as exc:
            self.log_line(f"lsof cleanup warning: {exc}")

    def profile_xml(self, slot_display: str) -> str:
        if slot_display in ("1", "2", "3", "4"):
            uuid = int(slot_display) - 1
            display_name = f"Controller {slot_display}"
        else:
            uuid = 1
            display_name = "Controller 2"
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<emulated_controller>
\t<type>Wii U GamePad</type>
\t<profile>{MANAGED_PROFILE_NAME}</profile>
\t<toggle_display>0</toggle_display>
\t<controller>
\t\t<api>DSUController</api>
\t\t<uuid>{uuid}</uuid>
\t\t<display_name>{display_name}</display_name>
\t\t<motion>false</motion>
\t\t<axis><deadzone>0.25</deadzone><range>1</range></axis>
\t\t<rotation><deadzone>0.25</deadzone><range>1</range></rotation>
\t\t<trigger><deadzone>0.25</deadzone><range>1</range></trigger>
\t\t<ip>127.0.0.1</ip>
\t\t<port>{self._selected_port()}</port>
\t\t<mappings />
\t</controller>
</emulated_controller>
'''

    def apply_cemu(self) -> None:
        try:
            CEMU_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
            # Preserve user mappings to avoid re-mapping after every restart.
            if MANAGED_PROFILE_PATH.exists():
                try:
                    tree = ET.parse(MANAGED_PROFILE_PATH)
                    root = tree.getroot()
                    controller = root.find("controller")
                    if controller is None:
                        raise RuntimeError("missing <controller> in profile")

                    api = controller.find("api")
                    if api is None:
                        api = ET.SubElement(controller, "api")
                    api.text = "DSUController"

                    uuid = controller.find("uuid")
                    if uuid is None:
                        uuid = ET.SubElement(controller, "uuid")
                    if self.slot_var.get() in ("1", "2", "3", "4"):
                        uuid.text = str(int(self.slot_var.get()) - 1)
                        display_name = f"Controller {self.slot_var.get()}"
                    else:
                        uuid.text = "1"
                        display_name = "Controller 2"

                    dn = controller.find("display_name")
                    if dn is None:
                        dn = ET.SubElement(controller, "display_name")
                    dn.text = display_name

                    ip = controller.find("ip")
                    if ip is None:
                        ip = ET.SubElement(controller, "ip")
                    ip.text = "127.0.0.1"

                    port = controller.find("port")
                    if port is None:
                        port = ET.SubElement(controller, "port")
                    port.text = str(self._selected_port())

                    tree.write(MANAGED_PROFILE_PATH, encoding="utf-8", xml_declaration=True)
                except Exception:
                    MANAGED_PROFILE_PATH.write_text(self.profile_xml(self.slot_var.get()), encoding="utf-8")
            else:
                MANAGED_PROFILE_PATH.write_text(self.profile_xml(self.slot_var.get()), encoding="utf-8")
            CEMU_CONTROLLER0.write_text(
                f'''<?xml version="1.0" encoding="UTF-8"?>\n<emulated_controller>\n\t<type>Wii U GamePad</type>\n\t<profile>{MANAGED_PROFILE_NAME}</profile>\n\t<toggle_display>0</toggle_display>\n</emulated_controller>\n''',
                encoding="utf-8",
            )
            self.log_line("Applied Cemu DSU profile (mappings preserved)")
        except Exception as exc:
            self.log_line(f"Could not apply Cemu profile: {exc}")

    def _bridge_thread_main(self) -> None:
        writer = QueueLogWriter(self.log_queue)
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = writer
        sys.stderr = writer
        try:
            DsuBridge = load_dsu_bridge_class()
            slot = int(self.selected_slot())
            slot_mode = -1 if slot == 0 else (slot - 1)
            l3_buttons = tuple(int(x.strip()) for x in self.l3_var.get().split(",") if x.strip())
            r3_buttons = tuple(int(x.strip()) for x in self.r3_var.get().split(",") if x.strip())
            self.bridge = DsuBridge(
                "127.0.0.1",
                self._selected_port(),
                int(self.fps_var.get()),
                30.0,
                slot_mode,
                self.verbose_var.get(),
                self.profile_var.get(),
                l3_buttons,
                r3_buttons,
                int(self.lx_axis_var.get()),
                int(self.ly_axis_var.get()),
                int(self.rx_axis_var.get()),
                int(self.ry_axis_var.get()),
                "stick" if self.gyro_emulation_var.get() else "off",
                float(self.gyro_strength_var.get()),
                True,
                True,
            )
            BRIDGE_PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
            self.bridge.run()
        except Exception as exc:
            self.log_queue.put(f"[bridge] Error: {exc}")
        finally:
            writer.flush()
            sys.stdout, sys.stderr = old_out, old_err
            self.bridge = None
            try:
                BRIDGE_PID_FILE.unlink(missing_ok=True)
            except OSError:
                pass

    def drain(self) -> None:
        processed = 0
        max_per_tick = 30
        while processed < max_per_tick:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_line(line)
            processed += 1

        if self.bridge_thread is not None and not self.bridge_thread.is_alive():
            self.status_var.set("Stopped")
            self.log_line("Bridge stopped")
            self.bridge_thread = None
            self.bridge = None
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")

        self.root.after(500, self.drain)

    def start(self) -> None:
        if self.bridge_thread is not None and self.bridge_thread.is_alive():
            return
        if not bridge_script_path().exists():
            messagebox.showerror("Missing file", f"Could not find:\n{bridge_script_path()}")
            self.log_line("Start failed: bridge script missing")
            return

        if self.auto_apply_var.get():
            self.apply_cemu()
        self.kill_stale()

        preferred_port = self._selected_port()
        free_port = self._find_available_port(preferred_port)
        if free_port != preferred_port:
            self.log_line(f"Port {preferred_port} busy. Keeping fixed port for stable Cemu mapping; stop other process and retry.")
            self.status_var.set("Port busy")
            return

        self.log_line("Starting bridge in-app (no extra Python process)")
        self.bridge_thread = threading.Thread(target=self._bridge_thread_main, daemon=True)
        self.bridge_thread.start()

        self.status_var.set("Running")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

    def _stop_bridge_process(self) -> None:
        if self.bridge is not None:
            self.log_line("Stopping bridge...")
            self.bridge.running = False
            try:
                self.bridge._save_persisted_clients()
            except Exception:
                pass
        if self.bridge_thread is not None and self.bridge_thread.is_alive():
            self.bridge_thread.join(timeout=3.0)
        self.bridge = None
        self.bridge_thread = None
        self.kill_stale()
        self.status_var.set("Stopped")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def stop(self) -> None:
        self._stop_bridge_process()

    def on_close(self) -> None:
        self._stop_bridge_process()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    BridgeUI().run()
