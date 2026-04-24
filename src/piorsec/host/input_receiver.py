"""
Input reception process (Host side).

Listens for input packets from the client on UDP port INPUT_PORT (5002).
Packet structure (8 bytes): session_id(H) | player_id(B) | event_type(B) | value(i)

In this mock phase the received events are only counted for the stats dashboard.
The real implementation will inject them via vgamepad / ctypes SendInput.
"""

import multiprocessing
import socket
import time

from piorsec.shared.config import UDP_BUFFER_SIZE
from piorsec.shared.protocol import INPUT_PACKET_SIZE, INPUT_PORT, unpack_input


def input_receiver(stats_queue: multiprocessing.Queue) -> None:
    """Receive input packets from the client and report event rate every second.

    Uses a 1-second socket timeout so the stats reporting loop ticks
    even when no input arrives.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", INPUT_PORT))
    sock.settimeout(1.0)

    event_count = 0
    stats_ts    = time.monotonic()

    while True:
        try:
            data, _addr = sock.recvfrom(UDP_BUFFER_SIZE)
        except (socket.timeout, TimeoutError):
            data = None

        if data and len(data) >= INPUT_PACKET_SIZE:
            _session_id, _player_id, _event_type, _value = unpack_input(data)
            event_count += 1

        now = time.monotonic()
        if now - stats_ts >= 1.0:
            elapsed = now - stats_ts
            stats_queue.put_nowait({"input_rx_eps": event_count / elapsed})
            event_count = 0
            stats_ts    = now
