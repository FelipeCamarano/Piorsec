"""
Input capture and transmission (Client side).

Captures keyboard and mouse events using pynput and sends them to the host
via UDP on INPUT_PORT (5002).
"""

import multiprocessing
import socket
import time

from pynput import keyboard, mouse

from piorsec.shared.protocol import INPUT_PORT, EventType, pack_input

_SESSION_ID = 0x0001
_PLAYER_ID = 0x01


def input_sender(host_ip: str, stats_queue: multiprocessing.Queue) -> None:
    """Capture local inputs and send to *host_ip*:INPUT_PORT.

    Parameters
    ----------
    host_ip:
        IP address of the host machine.
    stats_queue:
        Metrics for the stats dashboard.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    event_count = 0
    stats_count = 0
    stats_ts = time.monotonic()

    def _send(event_type: int, value: int) -> None:
        nonlocal event_count, stats_count
        packet = pack_input(_SESSION_ID, _PLAYER_ID, event_type, value)
        sock.sendto(packet, (host_ip, INPUT_PORT))
        event_count += 1
        stats_count += 1

    def _on_key_press(key) -> None:
        try:
            vk = key.vk
        except AttributeError:
            try:
                vk = key.value.vk
            except AttributeError:
                return
        if vk is not None:
            _send(EventType.KEY_DOWN, vk & 0xFF)

    def _on_key_release(key) -> None:
        try:
            vk = key.vk
        except AttributeError:
            try:
                vk = key.value.vk
            except AttributeError:
                return
        if vk is not None:
            _send(EventType.KEY_UP, vk & 0xFF)

    def _on_mouse_move(x, y) -> None:  # noqa: ARG001
        # Optional: send mouse axis events
        pass

    def _on_mouse_click(x, y, button, pressed) -> None:  # noqa: ARG001
        btn_map = {mouse.Button.left: 1, mouse.Button.right: 2, mouse.Button.middle: 3}
        btn = btn_map.get(button, 0)
        if pressed:
            _send(EventType.BTN_DOWN, btn)
        else:
            _send(EventType.BTN_UP, btn)

    key_listener = keyboard.Listener(on_press=_on_key_press, on_release=_on_key_release)
    mouse_listener = mouse.Listener(on_move=_on_mouse_move, on_click=_on_mouse_click)
    key_listener.start()
    mouse_listener.start()

    try:
        while True:
            time.sleep(0.1)
            now = time.monotonic()
            if now - stats_ts >= 1.0:
                elapsed = now - stats_ts
                try:
                    stats_queue.put_nowait({"input_tx_eps": stats_count / elapsed})
                except Exception:
                    pass
                stats_count = 0
                stats_ts = now
    finally:
        key_listener.stop()
        mouse_listener.stop()
