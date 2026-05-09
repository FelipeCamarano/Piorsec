"""
Input reception process (Host side).

Listens for input packets from the client on UDP port INPUT_PORT (5002).
Injects keyboard events via ctypes SendInput (Windows) and gamepad events
via vgamepad.

Packet structure (8 bytes): session_id(H) | player_id(B) | event_type(B) | value(i)
"""

import multiprocessing
import socket
import struct
import time

from piorsec.shared.config import UDP_BUFFER_SIZE
from piorsec.shared.protocol import INPUT_PACKET_SIZE, INPUT_PORT, EventType, unpack_input

# Windows-specific input injection
_SEND_INPUT_AVAILABLE = False
try:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    INPUT_KEYBOARD = 1
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", wintypes.ULONG_PTR),
        ]

    class INPUT_I(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("_input", INPUT_I)]

    def _send_input_key(vk: int, up: bool = False) -> None:
        flags = KEYEVENTF_KEYUP if up else 0
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp._input.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    _SEND_INPUT_AVAILABLE = True
except Exception:
    pass

_VGAMEPAD_AVAILABLE = False
try:
    import vgamepad as vg

    _gamepad = vg.VX360Gamepad()
    _VGAMEPAD_AVAILABLE = True
except Exception:
    _gamepad = None


def input_receiver(stats_queue: multiprocessing.Queue) -> None:
    """Receive input packets from the client and inject them locally.

    Parameters
    ----------
    stats_queue:
        Metrics for the stats dashboard.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", INPUT_PORT))
    sock.settimeout(1.0)

    event_count = 0
    stats_ts = time.monotonic()

    while True:
        try:
            data, _addr = sock.recvfrom(UDP_BUFFER_SIZE)
        except (socket.timeout, TimeoutError):
            data = None

        if data and len(data) >= INPUT_PACKET_SIZE:
            _session_id, _player_id, event_type, value = unpack_input(data)
            event_count += 1

            # Keyboard injection (Windows SendInput)
            if _SEND_INPUT_AVAILABLE:
                if event_type == EventType.KEY_DOWN:
                    _send_input_key(value & 0xFF)
                elif event_type == EventType.KEY_UP:
                    _send_input_key(value & 0xFF, up=True)

            # Gamepad injection (vgamepad)
            if _VGAMEPAD_AVAILABLE and _gamepad is not None:
                if event_type == EventType.BTN_DOWN:
                    btn = value & 0xFF
                    if btn == 1:
                        _gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
                    elif btn == 2:
                        _gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
                    elif btn == 3:
                        _gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_X)
                    _gamepad.update()
                elif event_type == EventType.BTN_UP:
                    btn = value & 0xFF
                    if btn == 1:
                        _gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
                    elif btn == 2:
                        _gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
                    elif btn == 3:
                        _gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_X)
                    _gamepad.update()
                elif event_type == EventType.AXIS:
                    # Normalize signed 16-bit to float -1..1
                    norm = value / 32767.0
                    _gamepad.left_joystick_float(x_value_f=norm, y_value_f=0.0)
                    _gamepad.update()

        now = time.monotonic()
        if now - stats_ts >= 1.0:
            elapsed = now - stats_ts
            try:
                stats_queue.put_nowait({"input_rx_eps": event_count / elapsed})
            except Exception:
                pass
            event_count = 0
            stats_ts = now
