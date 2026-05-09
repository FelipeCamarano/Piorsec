"""
Video and audio sender processes (Host side).

video_sender — reads encoded packets from a Queue, fragments when needed,
               and transmits via UDP to the client.
audio_sender — reads encoded audio packets from a Queue and sends them.

Both functions are top-level so they can be pickled by multiprocessing
on Windows (spawn start method).
"""

import math
import multiprocessing
import queue
import socket
import time

from piorsec.shared.config import UDP_BUFFER_SIZE
from piorsec.shared.protocol import (
    AUDIO_PORT,
    VIDEO_HEADER_SIZE,
    VIDEO_PORT,
    PayloadType,
    pack_audio,
    pack_video,
)

# Maximum bytes we can put in the UDP payload for a video fragment
_MAX_VIDEO_PAYLOAD = UDP_BUFFER_SIZE - VIDEO_HEADER_SIZE  # 65 495 B


def video_sender(
    client_ip: str,
    encoded_queue: multiprocessing.Queue,
    stats_queue: multiprocessing.Queue,
) -> None:
    """Send encoded video packets to *client_ip*:VIDEO_PORT."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    seq_num = 0
    stats_bytes = 0
    stats_frames = 0
    stats_ts = time.monotonic()

    while True:
        try:
            item = encoded_queue.get(timeout=0.010)
        except queue.Empty:
            continue

        if item is None:
            continue

        ptype, frame_data = item
        timestamp_ms = int(time.monotonic() * 1000) & 0xFFFF_FFFF
        total_frags = math.ceil(len(frame_data) / _MAX_VIDEO_PAYLOAD)

        for frag_idx in range(total_frags):
            chunk = frame_data[frag_idx * _MAX_VIDEO_PAYLOAD:(frag_idx + 1) * _MAX_VIDEO_PAYLOAD]
            packet = pack_video(seq_num, timestamp_ms, frag_idx, total_frags, chunk, ptype)
            sock.sendto(packet, (client_ip, VIDEO_PORT))
            stats_bytes += len(packet)
            seq_num = (seq_num + 1) & 0xFFFF

        stats_frames += 1

        now = time.monotonic()
        if now - stats_ts >= 1.0:
            elapsed = now - stats_ts
            try:
                stats_queue.put_nowait({
                    "video_tx_kbps": stats_bytes * 8 / elapsed / 1_000,
                    "video_tx_fps": stats_frames / elapsed,
                })
            except Exception:
                pass
            stats_bytes = 0
            stats_frames = 0
            stats_ts = now


def audio_sender(
    client_ip: str,
    audio_queue: multiprocessing.Queue,
    stats_queue: multiprocessing.Queue,
) -> None:
    """Send encoded audio packets to *client_ip*:AUDIO_PORT at 50 pps (20 ms interval)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    seq_num = 0
    stats_bytes = 0
    stats_pkts = 0
    stats_ts = time.monotonic()

    while True:
        try:
            payload = audio_queue.get(timeout=0.010)
        except queue.Empty:
            continue

        if payload is None:
            continue

        timestamp_ms = int(time.monotonic() * 1000) & 0xFFFF_FFFF
        packet = pack_audio(seq_num, timestamp_ms, payload)

        sock.sendto(packet, (client_ip, AUDIO_PORT))
        stats_bytes += len(packet)
        stats_pkts += 1
        seq_num = (seq_num + 1) & 0xFFFF

        now = time.monotonic()
        if now - stats_ts >= 1.0:
            elapsed = now - stats_ts
            try:
                stats_queue.put_nowait({
                    "audio_tx_kbps": stats_bytes * 8 / elapsed / 1_000,
                    "audio_tx_pps": stats_pkts / elapsed,
                })
            except Exception:
                pass
            stats_bytes = 0
            stats_pkts = 0
            stats_ts = now
