"""
Input capture and transmission (Client side).

Sends mock input events to the host at ~12 events/second using
deadline-based timing so the long-term average stays accurate.

In the real implementation pynput will replace mock_input_event().
"""

import multiprocessing
import random
import socket
import time

from piorsec.shared.mock import mock_input_event
from piorsec.shared.protocol import INPUT_PORT, pack_input

_SESSION_ID = 0x0001
_PLAYER_ID  = 0x01
_TARGET_EPS = 12          # target events per second


def input_sender(host_ip: str, stats_queue: multiprocessing.Queue) -> None:
    """Send mock input packets to *host_ip*:INPUT_PORT at ~12 eps."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    event_count = 0     # total events sent (for deadline timing)
    stats_count = 0     # events sent in the current stats window
    start_time  = time.perf_counter()
    stats_ts    = time.monotonic()

    while True:
        # Deadline-based timing — self-corrects over time
        deadline   = start_time + event_count / _TARGET_EPS
        sleep_time = deadline - time.perf_counter()
        if sleep_time > 0:
            time.sleep(sleep_time)

        event_type, value = mock_input_event()
        packet = pack_input(_SESSION_ID, _PLAYER_ID, event_type, value)
        sock.sendto(packet, (host_ip, INPUT_PORT))

        event_count += 1
        stats_count += 1

        now = time.monotonic()
        if now - stats_ts >= 1.0:
            elapsed = now - stats_ts
            stats_queue.put_nowait({"input_tx_eps": stats_count / elapsed})
            stats_count = 0
            stats_ts    = now
