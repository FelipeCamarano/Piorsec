"""
Video and audio receiver processes (Client side).

video_receiver — binds :VIDEO_PORT, receives RTP-like video packets,
                 tracks packet loss via seq_num gaps, reports stats.
audio_receiver — binds :AUDIO_PORT, receives audio packets, reports stats.

Both are top-level functions for multiprocessing compatibility on Windows.
"""

import multiprocessing
import socket
import time

from piorsec.shared.config import UDP_BUFFER_SIZE
from piorsec.shared.protocol import (
    AUDIO_PORT,
    VIDEO_PORT,
    unpack_audio,
    unpack_video,
)


def video_receiver(stats_queue: multiprocessing.Queue) -> None:
    """Receive video packets from the host and report throughput and loss every second."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", VIDEO_PORT))
    sock.settimeout(1.0)

    expected_seq: int | None = None
    total_bytes  = 0
    total_pkts   = 0
    lost_pkts    = 0
    stats_ts     = time.monotonic()

    while True:
        try:
            data, _addr = sock.recvfrom(UDP_BUFFER_SIZE)
        except (socket.timeout, TimeoutError):
            data = None

        if data:
            _version, _ptype, seq, _ts, _frag_idx, _total_frags, _payload = unpack_video(data)

            # Packet loss detection: count gaps in the sequence number
            if expected_seq is None:
                expected_seq = seq
            gap = (seq - expected_seq) & 0xFFFF
            if gap > 0:
                lost_pkts += gap
            expected_seq = (seq + 1) & 0xFFFF

            total_bytes += len(data)
            total_pkts  += 1

        now = time.monotonic()
        if now - stats_ts >= 1.0:
            elapsed    = now - stats_ts
            kbps       = total_bytes * 8 / elapsed / 1_000
            pps        = total_pkts / elapsed
            total_seen = total_pkts + lost_pkts
            loss_pct   = (lost_pkts / total_seen * 100) if total_seen > 0 else 0.0

            stats_queue.put_nowait({
                "video_rx_kbps":     kbps,
                "video_rx_pps":      pps,
                "video_rx_loss_pct": loss_pct,
            })

            total_bytes  = 0
            total_pkts   = 0
            lost_pkts    = 0
            stats_ts     = now


def audio_receiver(stats_queue: multiprocessing.Queue) -> None:
    """Receive audio packets from the host and report throughput every second."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", AUDIO_PORT))
    sock.settimeout(1.0)

    total_bytes = 0
    total_pkts  = 0
    stats_ts    = time.monotonic()

    while True:
        try:
            data, _addr = sock.recvfrom(UDP_BUFFER_SIZE)
        except (socket.timeout, TimeoutError):
            data = None

        if data:
            _version, _ptype, _seq, _ts, _payload = unpack_audio(data)
            total_bytes += len(data)
            total_pkts  += 1

        now = time.monotonic()
        if now - stats_ts >= 1.0:
            elapsed = now - stats_ts
            stats_queue.put_nowait({
                "audio_rx_kbps": total_bytes * 8 / elapsed / 1_000,
                "audio_rx_pps":  total_pkts / elapsed,
            })
            total_bytes = 0
            total_pkts  = 0
            stats_ts    = now
