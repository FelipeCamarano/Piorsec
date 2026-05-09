"""
Audio capture process (Host side).

Captures system audio using PyAudio from the default input device
(microphone or loopback device). Raw PCM stereo 48 kHz / 16-bit frames
are pushed to a Queue for the audio_sender process.
"""

import multiprocessing
import time

import pyaudio

from piorsec.shared.config import AUDIO_CHANNELS, AUDIO_SAMPLE_RATE

# 20 ms frame at 48 kHz stereo 16-bit
_FRAME_SAMPLES = int(AUDIO_SAMPLE_RATE * 0.020)  # 960
_FRAME_BYTES = _FRAME_SAMPLES * AUDIO_CHANNELS * 2  # 3840 bytes


def audio_capture(audio_queue: multiprocessing.Queue, stats_queue: multiprocessing.Queue) -> None:
    """Capture audio and push raw PCM frames to the sender queue.

    Parameters
    ----------
    audio_queue:
        Raw PCM bytes (960 samples × 2 ch × 2 bytes = 3840 B per frame).
    stats_queue:
        Metrics for the stats dashboard.
    """
    pa = pyaudio.PyAudio()

    # Try to find a loopback device on Windows; fallback to default input
    device_index = None
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        name = info["name"].lower()
        if "loopback" in name or "stereo mix" in name:
            if info["maxInputChannels"] >= AUDIO_CHANNELS:
                device_index = i
                break

    stream = pa.open(
        format=pyaudio.paInt16,
        channels=AUDIO_CHANNELS,
        rate=AUDIO_SAMPLE_RATE,
        input=True,
        input_device_index=device_index,
        frames_per_buffer=_FRAME_SAMPLES,
    )

    stats_pkts = 0
    stats_ts = time.monotonic()

    stream.start_stream()
    try:
        while True:
            data = stream.read(_FRAME_SAMPLES, exception_on_overflow=False)
            try:
                audio_queue.put_nowait(data)
            except Exception:
                pass  # drop if sender can't keep up
            stats_pkts += 1

            now = time.monotonic()
            if now - stats_ts >= 1.0:
                elapsed = now - stats_ts
                try:
                    stats_queue.put_nowait({
                        "audio_tx_kbps": stats_pkts * _FRAME_BYTES * 8 / elapsed / 1_000,
                        "audio_tx_pps": stats_pkts / elapsed,
                    })
                except Exception:
                    pass
                stats_pkts = 0
                stats_ts = now
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
