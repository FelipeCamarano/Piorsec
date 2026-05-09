"""
Video encoding process (Host side).

Reads raw BGRA frames from a Queue, encodes them using PyAV (FFmpeg),
and pushes encoded packets to another Queue for the sender process.

Primary codec: H.265/HEVC with GPU acceleration (NVENC/AMF).
Fallback codec: H.264/AVC for older hardware.
"""

import multiprocessing
import queue
import time

from fractions import Fraction

import av
import numpy as np

from piorsec.shared.config import VIDEO_BITRATE, VIDEO_CODEC_FALLBACK, VIDEO_CODEC_PRIMARY, VIDEO_FPS
from piorsec.shared.protocol import PayloadType


def _try_create_codec(codec_name: str, width: int, height: int) -> av.CodecContext | None:
    """Attempt to create an encoder; return None on failure."""
    try:
        ctx = av.CodecContext.create(codec_name, "w")
        ctx.width = width
        ctx.height = height
        ctx.pix_fmt = "yuv420p"
        ctx.time_base = Fraction(1, VIDEO_FPS)
        ctx.bit_rate = VIDEO_BITRATE
        ctx.gop_size = VIDEO_FPS * 2  # keyframe every 2 seconds
        ctx.framerate = Fraction(VIDEO_FPS, 1)
        # Hardware-specific options
        if "nvenc" in codec_name:
            ctx.options = {"preset": "p1", "tune": "ll", "rc": "cbr", "bitrate": str(VIDEO_BITRATE)}
        elif "amf" in codec_name:
            ctx.options = {"usage": "ultralowlatency", "rc": "cbr", "rate_control": "cbr"}
        else:
            ctx.options = {"preset": "ultrafast", "tune": "zerolatency"}
        ctx.open()
        return ctx
    except Exception:
        return None


def _create_encoder(width: int, height: int) -> av.CodecContext:
    """Create the best available encoder."""
    # 1. Try hardware H.265 encoders
    for codec_name in ("hevc_nvenc", "hevc_amf", "hevc_videotoolbox"):
        ctx = _try_create_codec(codec_name, width, height)
        if ctx is not None:
            return ctx
    # 2. Try hardware H.264 encoders (faster software fallback)
    for codec_name in ("h264_nvenc", "h264_amf", "h264_videotoolbox"):
        ctx = _try_create_codec(codec_name, width, height)
        if ctx is not None:
            return ctx
    # 3. Software H.264 (fastest software option for real-time)
    ctx = _try_create_codec("libx264", width, height)
    if ctx is not None:
        return ctx
    # 4. Software H.265 (last resort)
    ctx = _try_create_codec("libx265", width, height)
    if ctx is not None:
        return ctx
    raise RuntimeError("No video encoder available (tried HEVC/H.264 hardware and software).")


def video_encoder(
    raw_frame_queue: multiprocessing.Queue,
    encoded_queue: multiprocessing.Queue,
    stats_queue: multiprocessing.Queue,
) -> None:
    """Read raw frames, encode, and push encoded packets.

    Parameters
    ----------
    raw_frame_queue:
        BGRA numpy arrays from screen_capture.
    encoded_queue:
        Encoded bytes packets for video_sender.
    stats_queue:
        Metrics for the stats dashboard.
    """
    codec: av.CodecContext | None = None
    frame_count = 0
    encoded_frames = 0
    stats_ts = time.monotonic()

    while True:
        try:
            bgra = raw_frame_queue.get(timeout=0.010)
        except queue.Empty:
            continue

        if bgra is None:
            continue

        h, w, _channels = bgra.shape

        if codec is None:
            codec = _create_encoder(w, h)

        # Convert BGRA -> YUV420p via PyAV
        av_frame = av.VideoFrame.from_ndarray(bgra, format="bgra")
        av_frame.pts = frame_count
        av_frame.time_base = codec.time_base
        av_frame = av_frame.reformat(format="yuv420p", width=w, height=h)

        try:
            packets = codec.encode(av_frame)
        except Exception:
            packets = []

        for pkt in packets:
            # Determine payload type based on actual codec used
            if codec.name in ("hevc", "hevc_nvenc", "hevc_amf", "hevc_videotoolbox", "libx265"):
                ptype = PayloadType.VIDEO_H265
            else:
                ptype = PayloadType.VIDEO_H264
            try:
                encoded_queue.put_nowait((ptype, bytes(pkt)))
            except Exception:
                pass  # drop if sender can't keep up
            encoded_frames += 1

        frame_count += 1

        now = time.monotonic()
        if now - stats_ts >= 1.0:
            elapsed = now - stats_ts
            try:
                stats_queue.put_nowait({
                    "video_tx_fps": encoded_frames / elapsed,
                    "video_tx_kbps": 0.0,  # sender will report real bitrate
                })
            except Exception:
                pass
            encoded_frames = 0
            stats_ts = now
