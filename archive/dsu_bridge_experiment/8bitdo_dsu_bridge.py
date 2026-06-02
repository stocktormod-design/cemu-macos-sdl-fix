#!/usr/bin/env python3
import argparse
import atexit
import binascii
import hashlib
import os
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import pygame


PROTOCOL_VERSION = 1001
MSG_VERSION = 0x100000
MSG_PORT_INFO = 0x100001
MSG_PAD_DATA = 0x100002

CLIENTS_CACHE = Path.home() / "Library/Application Support/Cemu/8bitdo_dsu_clients.txt"
LSOF = "/usr/sbin/lsof"


def clamp_u8(value: float) -> int:
    return max(0, min(255, int(value)))


def axis_to_u8(raw: float) -> int:
    return clamp_u8((raw + 1.0) * 127.5)


def make_packet(server_id: int, msg_type: int, payload: bytes) -> bytes:
    body = struct.pack("<I", msg_type) + payload
    header = b"DSUS" + struct.pack("<HHII", PROTOCOL_VERSION, len(body), 0, server_id)
    pkt = bytearray(header + body)
    crc = binascii.crc32(pkt) & 0xFFFFFFFF
    struct.pack_into("<I", pkt, 8, crc)
    return bytes(pkt)


@dataclass
class Subscription:
    slot: Optional[int]  # None means all slots
    last_seen: float


class DsuBridge:
    def __init__(
        self,
        host: str,
        port: int,
        fps: int,
        timeout: float,
        slot_mode: int,
        verbose: bool,
        profile: str,
        l3_buttons: tuple[int, ...],
        r3_buttons: tuple[int, ...],
        lx_axis: int,
        ly_axis: int,
        rx_axis: int,
        ry_axis: int,
        gyro_source: str,
        gyro_strength: float,
        persist_clients: bool,
        embedded: bool = False,
        light_mode: bool = False,
    ) -> None:
        self.embedded = embedded
        self.light_mode = light_mode
        self.host = host
        self.port = port
        self.frame_sleep = 1.0 / max(1, fps)
        self.timeout = timeout
        self.slot_mode = slot_mode
        self.verbose = verbose
        self.profile = profile
        self.l3_buttons = l3_buttons
        self.r3_buttons = r3_buttons
        self.persist_clients = persist_clients
        self.server_id = 0x38424453
        self.lx_axis = lx_axis
        self.ly_axis = ly_axis
        self.rx_axis = rx_axis
        self.ry_axis = ry_axis
        self.gyro_source = gyro_source
        self.gyro_strength = max(0.1, float(gyro_strength))
        self.last_state = None
        self.last_buttons_sig = (0, 0, 0)
        self.last_send_ts = 0.0
        self.input_burst_until = 0.0
        self.packet_counter = int(time.time() * 1000) & 0xFFFFFFFF
        self.running = True
        self.joy: Optional[pygame.joystick.Joystick] = None
        self.fake_mac = b"\x38\x42\x44\x53\x00\x01"
        self.last_hotplug_scan = 0.0
        self.last_cemu_scan = 0.0
        self.last_subscribe_log: Dict[Tuple[str, int, str], float] = {}
        self.receiver_started = False

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.sock.settimeout(0.25)

        self.subscribers: Dict[Tuple[str, int], Subscription] = {}
        self.sub_lock = threading.Lock()
        self.last_stats_print = 0.0

        if not self.embedded:
            atexit.register(self._save_persisted_clients)
            signal.signal(signal.SIGTERM, self._on_shutdown_signal)
            signal.signal(signal.SIGINT, self._on_shutdown_signal)

        self._start_receiver()
        self._init_pygame()
        if self.persist_clients:
            self._load_persisted_clients()
        if not self.light_mode:
            self._discover_cemu_clients(force_log=True)
        self._try_init_joystick(force_log=True)

    def _on_shutdown_signal(self, _signum, _frame) -> None:
        self.running = False
        self._save_persisted_clients()

    def _start_receiver(self) -> None:
        if self.receiver_started:
            return
        self.receiver_started = True
        threading.Thread(target=self._receiver_loop, daemon=True).start()

    def _init_pygame(self) -> None:
        os.environ.setdefault("SDL_JOYSTICK_HIDAPI", "1")
        os.environ.setdefault("SDL_JOYSTICK_HIDAPI_SWITCH", "1")
        if self.embedded:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()
        pygame.joystick.init()

    def _discover_cemu_clients(self, force_log: bool = False) -> int:
        if self.light_mode:
            return 0
        now = time.monotonic()
        with self.sub_lock:
            has_subs = bool(self.subscribers)
        scan_interval = 8.0 if has_subs else 3.0
        if not force_log and (now - self.last_cemu_scan) < scan_interval:
            return 0
        self.last_cemu_scan = now
        if not Path(LSOF).exists():
            return 0

        found = 0
        try:
            out = subprocess.check_output([LSOF, "-nP", "-iUDP"], text=True, stderr=subprocess.DEVNULL)
        except Exception:
            return 0

        for line in out.splitlines():
            if "Cemu" not in line:
                continue
            parts = line.split()
            if len(parts) < 9:
                continue
            endpoint = parts[-1]
            if endpoint.startswith("UDP"):
                continue
            if ":" not in endpoint:
                continue
            host, port_s = endpoint.rsplit(":", 1)
            try:
                port = int(port_s)
            except ValueError:
                continue
            if port == self.port:
                continue
            host = "127.0.0.1" if host in ("*", "0.0.0.0") else host
            if not host.startswith("127."):
                continue
            addr = (host, port)
            with self.sub_lock:
                is_new = addr not in self.subscribers
                self.subscribers.setdefault(addr, Subscription(slot=None, last_seen=time.time()))
            if is_new:
                found += 1
                self._announce_to_client(addr)
                print(f"[bridge] Auto-linked Cemu UDP client {host}:{port}")

        if found:
            self.last_state = None
            self.last_send_ts = 0.0
            self._save_persisted_clients()
        elif force_log:
            print("[bridge] No Cemu UDP client found yet (start Cemu, then bridge will auto-link)")
        return found

    def _announce_to_client(self, addr: Tuple[str, int]) -> None:
        for slot in range(4):
            out_payload = self._base_pad_header(slot) + b"\x00"
            pkt = make_packet(self.server_id, MSG_PORT_INFO, out_payload)
            try:
                self.sock.sendto(pkt, addr)
            except OSError:
                pass
        self.last_state = None
        self.last_send_ts = 0.0

    def _try_init_joystick(self, force_log: bool = False) -> bool:
        now = time.monotonic()
        if self.joy is not None:
            try:
                _ = self.joy.get_name()
                return True
            except Exception:
                self.joy = None
                self.last_state = None

        if not force_log and (now - self.last_hotplug_scan) < 0.5:
            return False
        self.last_hotplug_scan = now

        pygame.event.pump()
        for event in pygame.event.get():
            if event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                if force_log:
                    print(f"[bridge] Joystick event: {event.type}")

        try:
            count = pygame.joystick.get_count()
            if count < 1:
                if force_log:
                    print("[bridge] Waiting for controller...")
                return False

            pick = 0
            for i in range(count):
                candidate = pygame.joystick.Joystick(i)
                candidate.init()
                name = (candidate.get_name() or "").lower()
                if "8bitdo" in name or "ultimate" in name or "pro" in name:
                    pick = i
                    break

            joy = pygame.joystick.Joystick(pick)
            joy.init()
            self.joy = joy
            self.last_state = None
            print(f"[bridge] Using controller: {joy.get_name()}")
            print(f"[bridge] Axes: {joy.get_numaxes()}, Buttons: {joy.get_numbuttons()}, Hats: {joy.get_numhats()}")
            self._discover_cemu_clients(force_log=True)
            return True
        except Exception as exc:
            if force_log:
                print(f"[bridge] Waiting for controller... ({exc})")
            self.joy = None
            return False

    def _load_persisted_clients(self) -> None:
        if not self.persist_clients or not CLIENTS_CACHE.exists():
            return
        try:
            now = time.time()
            loaded = 0
            with self.sub_lock:
                for line in CLIENTS_CACHE.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if ":" not in line:
                        continue
                    host, port_s = line.rsplit(":", 1)
                    addr = (host.strip(), int(port_s.strip()))
                    self.subscribers.setdefault(addr, Subscription(slot=None, last_seen=now))
                    loaded += 1
            if loaded:
                print(f"[bridge] Restored {loaded} known Cemu client(s) from cache")
        except Exception as exc:
            print(f"[bridge] Could not load client cache: {exc}")

    def _save_persisted_clients(self) -> None:
        if not self.persist_clients:
            return
        try:
            with self.sub_lock:
                lines = [f"{addr[0]}:{addr[1]}\n" for addr in self.subscribers.keys()]
            CLIENTS_CACHE.parent.mkdir(parents=True, exist_ok=True)
            CLIENTS_CACHE.write_text("".join(lines), encoding="utf-8")
        except Exception:
            pass

    def _touch_subscriber(self, addr: Tuple[str, int], slot: Optional[int]) -> None:
        with self.sub_lock:
            self.subscribers[addr] = Subscription(slot=slot, last_seen=time.time())
        self.last_state = None
        self.last_send_ts = 0.0
        self._save_persisted_clients()
        slot_text = "all" if slot is None else str(slot)
        now = time.monotonic()
        key = (addr[0], addr[1], slot_text)
        last = self.last_subscribe_log.get(key, 0.0)
        if now - last >= 1.0:
            print(f"[bridge] Cemu linked {addr[0]}:{addr[1]} slot={slot_text}")
            self.last_subscribe_log[key] = now

    def _base_pad_header(self, slot: int) -> bytes:
        return struct.pack("<BBBB", slot, 2, 1, 2) + self.fake_mac + struct.pack("<B", 0x05)

    def _handle_port_info_request(self, addr: Tuple[str, int], payload: bytes) -> None:
        self._touch_subscriber(addr, None)
        if len(payload) < 4:
            return
        count = struct.unpack_from("<i", payload, 0)[0]
        if count < 0:
            return
        for i in range(min(count, 4)):
            if 4 + i >= len(payload):
                break
            slot = payload[4 + i]
            if slot > 3:
                continue
            out_payload = self._base_pad_header(slot) + b"\x00"
            pkt = make_packet(self.server_id, MSG_PORT_INFO, out_payload)
            self.sock.sendto(pkt, addr)

    def _handle_data_subscribe(self, addr: Tuple[str, int], payload: bytes) -> None:
        slot: Optional[int] = None
        if len(payload) >= 1:
            flags = payload[0]
            if flags & 0x01 and len(payload) >= 2:
                req_slot = payload[1]
                if req_slot <= 3:
                    slot = req_slot
            elif flags & 0x02 and len(payload) >= 8:
                mac = payload[2:8]
                if mac == self.fake_mac:
                    slot = self.slot_mode if self.slot_mode >= 0 else None
        self._touch_subscriber(addr, slot)
        self._announce_to_client(addr)

    def _mark_input_burst(self, seconds: float = 0.2) -> None:
        self.input_burst_until = max(self.input_burst_until, time.monotonic() + seconds)

    def _pump_events(self) -> None:
        pygame.event.pump()
        for event in pygame.event.get():
            if event.type in (
                pygame.JOYBUTTONDOWN,
                pygame.JOYBUTTONUP,
                pygame.JOYAXISMOTION,
                pygame.JOYHATMOTION,
                pygame.JOYDEVICEADDED,
            ):
                self._mark_input_burst(0.25)

    def _read_hat(self) -> Tuple[bool, bool, bool, bool]:
        left = down = right = up = False
        if self.joy is not None and self.joy.get_numhats() > 0:
            hx, hy = self.joy.get_hat(0)
            left = hx < 0
            right = hx > 0
            down = hy < 0
            up = hy > 0
        return left, down, right, up

    def _btn_any(self, indices) -> bool:
        if self.joy is None:
            return False
        for idx in indices:
            if idx < self.joy.get_numbuttons() and self.joy.get_button(idx):
                return True
        return False

    def _axis(self, idx: int, default: float = 0.0) -> float:
        if self.joy is not None and idx < self.joy.get_numaxes():
            return float(self.joy.get_axis(idx))
        return default

    def _pressed_button_indices(self):
        if self.joy is None:
            return []
        return [i for i in range(self.joy.get_numbuttons()) if self.joy.get_button(i)]

    def _neutral_state(self) -> dict:
        now_us = int(time.time() * 1_000_000)
        return {
            "bm1": 0,
            "bm2": 0,
            "home": 0,
            "sticks": (127, 127, 127, 127),
            "analog": bytes(12),
            "motion": struct.pack("<Qffffff", now_us, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
            "debug_l3": 0,
            "debug_r3": 0,
            "debug_gx": 0.0,
            "debug_gy": 0.0,
        }

    def _read_state(self, poll_input: bool = True) -> dict:
        if poll_input and self.joy is None:
            self._try_init_joystick()
        if self.joy is not None and poll_input:
            try:
                self._pump_events()
            except Exception:
                self.joy = None
                self.last_state = None
                return self._neutral_state()
        else:
            return self._neutral_state()

        try:
            return self._read_state_inner()
        except Exception:
            self.joy = None
            self.last_state = None
            return self._neutral_state()

    def _read_state_inner(self) -> dict:
        if self.profile == "8bitdo":
            a = self._btn_any([1])
            b = self._btn_any([0])
            x = self._btn_any([3])
            y = self._btn_any([2])
            l1 = self._btn_any([4])
            r1 = self._btn_any([5])
            share = self._btn_any([6])
            options = self._btn_any([7])
            home = self._btn_any([8])
            l3 = self._btn_any(self.l3_buttons)
            r3 = self._btn_any(self.r3_buttons)
        else:
            a = self._btn_any([0])
            b = self._btn_any([1])
            x = self._btn_any([2])
            y = self._btn_any([3])
            l1 = self._btn_any([4])
            r1 = self._btn_any([5])
            share = self._btn_any([6])
            options = self._btn_any([7])
            home = self._btn_any([8])
            l3 = self._btn_any([9])
            r3 = self._btn_any([10])

        dleft, ddown, dright, dup = self._read_hat()
        lx = axis_to_u8(self._axis(self.lx_axis))
        ly = axis_to_u8(-self._axis(self.ly_axis))
        rx = axis_to_u8(self._axis(self.rx_axis))
        ry = axis_to_u8(-self._axis(self.ry_axis))
        l2_analog = axis_to_u8(self._axis(4))
        r2_analog = axis_to_u8(self._axis(5))
        l2 = l2_analog > 30
        r2 = r2_analog > 30

        bm1 = (
            (1 if dleft else 0) << 7
            | (1 if ddown else 0) << 6
            | (1 if dright else 0) << 5
            | (1 if dup else 0) << 4
            | (1 if options else 0) << 3
            | (1 if r3 else 0) << 2
            | (1 if l3 else 0) << 1
            | (1 if share else 0)
        )
        bm2 = (
            (1 if y else 0) << 7
            | (1 if b else 0) << 6
            | (1 if a else 0) << 5
            | (1 if x else 0) << 4
            | (1 if r1 else 0) << 3
            | (1 if l1 else 0) << 2
            | (1 if r2 else 0) << 1
            | (1 if l2 else 0)
        )
        analog = bytes(
            [
                255 if dleft else 0,
                255 if ddown else 0,
                255 if dright else 0,
                255 if dup else 0,
                255 if y else 0,
                255 if b else 0,
                255 if a else 0,
                255 if x else 0,
                255 if r1 else 0,
                255 if l1 else 0,
                r2_analog,
                l2_analog,
            ]
        )

        now_us = int(time.time() * 1_000_000)
        if self.gyro_source == "stick":
            gx = ((rx - 127.5) / 127.5) * self.gyro_strength
            gy = ((ry - 127.5) / 127.5) * self.gyro_strength
            gz = 0.0
        else:
            gx = gy = gz = 0.0
        motion = struct.pack("<Qffffff", now_us, 0.0, 0.0, 1.0, gx, gy, gz)

        return {
            "bm1": bm1,
            "bm2": bm2,
            "home": 1 if home else 0,
            "sticks": (lx, ly, rx, ry),
            "analog": analog,
            "motion": motion,
            "debug_l3": int(l3),
            "debug_r3": int(r3),
            "debug_gx": gx,
            "debug_gy": gy,
        }

    def _slots_for_subscriber(self, sub: Subscription) -> Tuple[int, ...]:
        if self.slot_mode == -1:
            if sub.slot is None:
                return (0, 1, 2, 3)
            return (sub.slot,)
        if sub.slot is None or sub.slot == self.slot_mode:
            return (self.slot_mode,)
        return ()

    def _build_pad_data_payload(self, slot: int, state: dict) -> bytes:
        payload = bytearray()
        payload.extend(self._base_pad_header(slot))
        payload.extend(struct.pack("<B", 1))
        payload.extend(struct.pack("<I", self.packet_counter))
        payload.extend(struct.pack("<BB", state["bm1"], state["bm2"]))
        payload.extend(struct.pack("<BB", state["home"], 0))
        payload.extend(struct.pack("<BBBB", *state["sticks"]))
        payload.extend(state["analog"])
        payload.extend(b"\x00\x00\x00\x00\x00\x00" * 2)
        payload.extend(state["motion"])
        return bytes(payload)

    def _stick_active(self, state: dict) -> bool:
        # Wider deadzone avoids drift keeping the bridge in high-power mode.
        for value in state["sticks"]:
            if abs(value - 127) > 24:
                return True
        return False

    def _should_send(self, state: dict, loop_now: float) -> Tuple[bool, bool]:
        state_sig = (state["bm1"], state["bm2"], state["home"], state["sticks"], state["analog"])
        buttons_sig = (state["bm1"], state["bm2"], state["home"])
        button_edge = buttons_sig != self.last_buttons_sig
        self.last_buttons_sig = buttons_sig

        active = buttons_sig != (0, 0, 0) or self._stick_active(state)
        burst = loop_now < self.input_burst_until
        changed = state_sig != self.last_state
        keepalive = (loop_now - self.last_send_ts) >= 1.0

        if button_edge or active or burst:
            return True, button_edge
        if changed or keepalive:
            return True, False
        return False, False

    def _prune_subscribers(self) -> None:
        now = time.time()
        with self.sub_lock:
            dead = [addr for addr, sub in self.subscribers.items() if now - sub.last_seen > self.timeout]
            for addr in dead:
                del self.subscribers[addr]

    def _send_updates(self) -> int:
        with self.sub_lock:
            subs = list(self.subscribers.items())
        if not subs:
            return 0

        loop_now = time.monotonic()
        since_send = loop_now - self.last_send_ts
        burst = loop_now < self.input_burst_until
        # Idle: skip pygame polling most frames; still wake for keepalive.
        if not burst and since_send < 0.04 and since_send < 0.95:
            return 0

        state = self._read_state(poll_input=True)
        state_sig = (state["bm1"], state["bm2"], state["home"], state["sticks"], state["analog"])
        should_send, button_edge = self._should_send(state, loop_now)
        if not should_send:
            return 0

        # Duplicate packet on button edge helps Cemu mapping catch short taps.
        send_passes = 2 if button_edge else 1
        sent = 0
        for _ in range(send_passes):
            self.packet_counter = (self.packet_counter + 1) & 0xFFFFFFFF
            for addr, sub in subs:
                slots = self._slots_for_subscriber(sub)
                for out_slot in slots:
                    payload = self._build_pad_data_payload(slot=out_slot, state=state)
                    pkt = make_packet(self.server_id, MSG_PAD_DATA, payload)
                    self.sock.sendto(pkt, addr)
                    sent += 1
        self.last_state = state_sig
        self.last_send_ts = loop_now

        now = time.time()
        if self.verbose and now - self.last_stats_print >= 5.0:
            pressed = self._pressed_button_indices()
            lx, ly, _, _ = state["sticks"]
            print(
                f"[bridge] sent={sent} subs={len(subs)} joy={'yes' if self.joy else 'no'} "
                f"lx={lx} ly={ly} pressed={pressed}"
            )
            self.last_stats_print = now
        return sent

    def _receiver_loop(self) -> None:
        print(f"[bridge] DSU server listening on {self.host}:{self.port}")
        if self.slot_mode == -1:
            print("[bridge] Slot mode: auto (broadcast to DSU1-DSU4)")
        else:
            print(f"[bridge] Slot mode: fixed (DSU{self.slot_mode + 1})")
        while self.running:
            try:
                data, addr = self.sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break

            if len(data) < 20 or data[0:4] != b"DSUC":
                continue
            version, payload_len = struct.unpack_from("<HH", data, 4)
            if version != PROTOCOL_VERSION:
                continue
            if payload_len + 16 > len(data):
                continue

            msg_type = struct.unpack_from("<I", data, 16)[0]
            payload = data[20 : 16 + payload_len]

            if msg_type == MSG_PORT_INFO:
                self._handle_port_info_request(addr, payload)
            elif msg_type == MSG_PAD_DATA:
                self._handle_data_subscribe(addr, payload)

    def run(self) -> None:
        try:
            while self.running:
                if not self.light_mode:
                    self._discover_cemu_clients()
                self._prune_subscribers()
                if self.joy is None:
                    self._try_init_joystick()
                sent = self._send_updates()
                if sent > 0:
                    time.sleep(self.frame_sleep)
                elif self.subscribers:
                    time.sleep(0.12)
                else:
                    time.sleep(0.4)
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            self._save_persisted_clients()
            try:
                self.sock.close()
            except OSError:
                pass
            if self.embedded:
                try:
                    pygame.joystick.quit()
                except Exception:
                    pass
            else:
                pygame.quit()
            print("\n[bridge] Stopped.")


def main() -> int:
    parser = argparse.ArgumentParser(description="8BitDo -> DSU bridge for Cemu (macOS)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=26760)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--slot", type=int, choices=[0, 1, 2, 3, 4], default=0)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--profile", choices=["8bitdo", "standard"], default="8bitdo")
    parser.add_argument("--l3-buttons", default="13,9,11,10,12,14")
    parser.add_argument("--r3-buttons", default="14,10,12,9,11,13")
    parser.add_argument("--lx-axis", type=int, default=0)
    parser.add_argument("--ly-axis", type=int, default=1)
    parser.add_argument("--rx-axis", type=int, default=2)
    parser.add_argument("--ry-axis", type=int, default=3)
    parser.add_argument("--gyro-source", choices=["off", "stick"], default="off")
    parser.add_argument("--gyro-strength", type=float, default=2.4)
    parser.add_argument("--no-persist-clients", action="store_true")
    parser.add_argument("--light", action="store_true", help="Low CPU: no lsof Cemu scan, no client cache")
    args = parser.parse_args()

    try:
        slot_mode = -1 if args.slot == 0 else (args.slot - 1)
        l3_buttons = tuple(int(x.strip()) for x in args.l3_buttons.split(",") if x.strip())
        r3_buttons = tuple(int(x.strip()) for x in args.r3_buttons.split(",") if x.strip())
        bridge = DsuBridge(
            args.host,
            args.port,
            args.fps,
            args.timeout,
            slot_mode,
            args.verbose,
            args.profile,
            l3_buttons,
            r3_buttons,
            args.lx_axis,
            args.ly_axis,
            args.rx_axis,
            args.ry_axis,
            args.gyro_source,
            args.gyro_strength,
            persist_clients=False if (args.no_persist_clients or args.light) else True,
            light_mode=args.light,
        )
        bridge.run()
        return 0
    except Exception as exc:
        print(f"[bridge] Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
