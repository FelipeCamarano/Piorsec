"""
Screen capture process (Host side).

Uses MSS (Multiple ScreenShots) to capture frames from the primary monitor
at high speed via ctypes. Captured raw BGRA frames are placed into a
multiprocessing Queue for the encoder process.
"""

import multiprocessing
import time

import mss
import numpy as np

from piorsec.shared.config import VIDEO_FPS


def screen_capture(frame_queue: multiprocessing.Queue) -> None:
    """Capture the primary monitor at VIDEO_FPS and push raw BGRA frames.

    Parameters
    ----------
    frame_queue:
        Queue of numpy ndarray (H×W×4 uint8 BGRA) consumed by the encoder.
        Frames are dropped if the queue is full to avoid backpressure.
    """
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # primary monitor
        interval = 1.0 / VIDEO_FPS
        next_capture = time.perf_counter()

        while True:
            now = time.perf_counter()
            sleep_time = next_capture - now
            if sleep_time > 0:
                time.sleep(sleep_time)

            img = sct.grab(monitor)
            frame = np.array(img, dtype=np.uint8)

            try:
                frame_queue.put_nowait(frame)
            except Exception:
                pass  # drop frame if encoder can't keep up

            next_capture += interval
