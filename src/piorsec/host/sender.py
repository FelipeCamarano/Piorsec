"""
Video and audio sender processes (Host side).

video_sender — captures mock frames at 60 fps, fragments when needed,
               and transmits via UDP to the client.
audio_sender — sends mock Opus frames at 50 pps (every 20 ms).

Both functions are top-level so they can be pickled by multiprocessing
on Windows (spawn start method).
"""

import math
import multiprocessing
import socket
import time

from piorsec.shared.config import UDP_BUFFER_SIZE, VIDEO_FPS
from piorsec.shared.mock import mock_audio_frame, mock_video_frame
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

# I-frame every N frames (2 s at 60 fps)
_KEYFRAME_INTERVAL = 120


def video_sender(client_ip: str, stats_queue: multiprocessing.Queue) -> None:
    """Send mock video frames to *client_ip*:VIDEO_PORT at VIDEO_FPS.

    Uses deadline-based timing to maintain a stable frame rate.
    Frames larger than _MAX_VIDEO_PAYLOAD are split into multiple UDP packets.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    seq_num     = 0
    frame_count = 0
    start_time  = time.perf_counter()

    # Stats accumulators — reset every second
    stats_bytes  = 0
    stats_frames = 0
    stats_ts     = time.monotonic()

    while True:
        # Sleep until the next frame deadline
        deadline   = start_time + frame_count / VIDEO_FPS
        sleep_time = deadline - time.perf_counter()
        if sleep_time > 0:
            time.sleep(sleep_time)

        is_keyframe  = (frame_count % _KEYFRAME_INTERVAL == 0)
        frame_data   = mock_video_frame(is_keyframe)
        timestamp_ms = int(time.monotonic() * 1000) & 0xFFFF_FFFF
        ptype        = PayloadType.VIDEO_H265

        total_frags = math.ceil(len(frame_data) / _MAX_VIDEO_PAYLOAD)

        for frag_idx in range(total_frags):
            chunk  = frame_data[frag_idx * _MAX_VIDEO_PAYLOAD:(frag_idx + 1) * _MAX_VIDEO_PAYLOAD]
            packet = pack_video(seq_num, timestamp_ms, frag_idx, total_frags, chunk, ptype)
            sock.sendto(packet, (client_ip, VIDEO_PORT))
            stats_bytes += len(packet)
            seq_num = (seq_num + 1) & 0xFFFF

        stats_frames += 1
        frame_count  += 1

        # Report once per second
        now = time.monotonic()
        if now - stats_ts >= 1.0:
            elapsed = now - stats_ts
            stats_queue.put_nowait({
                "video_tx_kbps": stats_bytes * 8 / elapsed / 1_000,
                "video_tx_fps":  stats_frames / elapsed,
            })
            stats_bytes  = 0
            stats_frames = 0
            stats_ts     = now


def audio_sender(client_ip: str, stats_queue: multiprocessing.Queue) -> None:
    """Send mock Opus audio frames to *client_ip*:AUDIO_PORT at 50 pps (20 ms interval)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    seq_num    = 0
    pkt_count  = 0
    start_time = time.perf_counter()

    stats_bytes = 0
    stats_pkts  = 0
    stats_ts    = time.monotonic()

    _INTERVAL = 0.020   # 20 ms — one Opus frame

    while True:
        deadline   = start_time + pkt_count * _INTERVAL
        sleep_time = deadline - time.perf_counter()
        if sleep_time > 0:
            time.sleep(sleep_time)

        payload      = mock_audio_frame()
        timestamp_ms = int(time.monotonic() * 1000) & 0xFFFF_FFFF
        packet       = pack_audio(seq_num, timestamp_ms, payload)

        sock.sendto(packet, (client_ip, AUDIO_PORT))
        stats_bytes += len(packet)
        stats_pkts  += 1
        seq_num      = (seq_num + 1) & 0xFFFF
        pkt_count   += 1

        now = time.monotonic()
        if now - stats_ts >= 1.0:
            elapsed = now - stats_ts
            stats_queue.put_nowait({
                "audio_tx_kbps": stats_bytes * 8 / elapsed / 1_000,
                "audio_tx_pps":  stats_pkts / elapsed,
            })
            stats_bytes = 0
            stats_pkts  = 0
            stats_ts    = now
