"""
Audio playback (Client side).

Receives raw PCM audio from the host via Queue and plays it back
in real time using PyAudio.
"""

import multiprocessing
import queue
import time

import pyaudio

from piorsec.shared.config import AUDIO_CHANNELS, AUDIO_SAMPLE_RATE

# 20 ms frame at 48 kHz stereo 16-bit
_FRAME_SAMPLES = int(AUDIO_SAMPLE_RATE * 0.020)  # 960
_FRAME_BYTES = _FRAME_SAMPLES * AUDIO_CHANNELS * 2  # 3840 bytes


def audio_output(audio_queue: multiprocessing.Queue, stats_queue: multiprocessing.Queue) -> None:
    """Play back raw PCM audio frames received from the host.

    Parameters
    ----------
    audio_queue:
        Raw PCM bytes (960 samples × 2 ch × 2 bytes = 3840 B per frame).
    stats_queue:
        Metrics for the stats dashboard.
    """
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=AUDIO_CHANNELS,
        rate=AUDIO_SAMPLE_RATE,
        output=True,
        frames_per_buffer=_FRAME_SAMPLES * 2,
    )

    stats_pkts = 0
    stats_ts = time.monotonic()

    stream.start_stream()
    try:
        while True:
            try:
                data = audio_queue.get(timeout=0.020)
            except queue.Empty:
                # Write silence to avoid underrun clicks
                data = b"\x00" * _FRAME_BYTES

            if data is not None and len(data) == _FRAME_BYTES:
                stream.write(data)
                stats_pkts += 1

            now = time.monotonic()
            if now - stats_ts >= 1.0:
                elapsed = now - stats_ts
                try:
                    stats_queue.put_nowait({
                        "audio_rx_kbps": stats_pkts * _FRAME_BYTES * 8 / elapsed / 1_000,
                        "audio_rx_pps": stats_pkts / elapsed,
                    })
                except Exception:
                    pass
                stats_pkts = 0
                stats_ts = now
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
