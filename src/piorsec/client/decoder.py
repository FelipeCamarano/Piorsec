"""
Video decoding process (Client side).

Reads raw RTP-like packets from a Queue, reassembles fragmented frames,
decodes H.265/H.264 via PyAV, and enqueues RGB numpy arrays for display.
"""

import multiprocessing
import queue
import time
from collections import defaultdict

import av
import numpy as np

from piorsec.shared.protocol import PayloadType, unpack_video


def video_decoder(
    packet_queue: multiprocessing.Queue,
    frame_queue: multiprocessing.Queue,
    stats_queue: multiprocessing.Queue,
) -> None:
    """Decode incoming video packets and push RGB frames to the GUI.

    Parameters
    ----------
    packet_queue:
        Raw UDP packets produced by video_receiver.
    frame_queue:
        Decoded RGB frames (numpy ndarray) consumed by the GUI.
        Should be created with maxsize=2 to keep latency low.
    stats_queue:
        Metric dicts forwarded to the stats dashboard.
    """
    codec = av.CodecContext.create("hevc", "r")
    # Allow fallback to h264 if the first frames indicate so (handled by extradata / parse)

    # Reassembly state: timestamp_ms -> {fragments[], total_frags, received_count}
    pending: dict[int, dict] = defaultdict(lambda: {"frags": {}, "total": None, "ts": 0.0})

    decoded_frames = 0
    decoded_bytes  = 0
    stats_ts       = time.monotonic()

    while True:
        # Drain as many packets as available without blocking indefinitely
        try:
            data = packet_queue.get(timeout=0.010)
        except queue.Empty:
            data = None

        if data:
            _version, payload_type, _seq, timestamp_ms, frag_idx, total_frags, payload = unpack_video(data)

            # Update codec context if payload type changes (e.g., H.264 after H.265)
            if payload_type == PayloadType.VIDEO_H264 and codec.name != "h264":
                codec = av.CodecContext.create("h264", "r")

            frame_info = pending[timestamp_ms]
            frame_info["total"] = total_frags
            frame_info["ts"] = time.monotonic()
            frame_info["frags"][frag_idx] = payload

            # Check if frame is complete
            if len(frame_info["frags"]) == total_frags:
                # Reassemble
                chunks = [frame_info["frags"][i] for i in range(total_frags)]
                frame_data = b"".join(chunks)
                del pending[timestamp_ms]

                # Decode
                try:
                    packets = codec.parse(frame_data)
                    for pkt in packets:
                        for av_frame in codec.decode(pkt):
                            # Convert to RGB numpy array
                            rgb_frame = av_frame.reformat(format="rgb24")
                            nd = rgb_frame.to_ndarray()

                            # Push to GUI queue (drop if full to minimize latency)
                            try:
                                frame_queue.put_nowait(nd)
                            except Exception:
                                pass  # frame dropped

                            decoded_frames += 1
                except Exception:
                    # Corrupted frame or codec error — skip
                    pass

        # Prune stale incomplete frames (older than 500 ms)
        now = time.monotonic()
        stale = [ts for ts, info in pending.items() if now - info["ts"] > 0.5]
        for ts in stale:
            del pending[ts]

        # Report decoder stats once per second
        if now - stats_ts >= 1.0:
            elapsed = now - stats_ts
            try:
                stats_queue.put_nowait({
                    "decoder_fps": decoded_frames / elapsed,
                })
            except Exception:
                pass
            decoded_frames = 0
            decoded_bytes  = 0
            stats_ts = now
