"""
Live terminal stats dashboard for the Piorsec pipeline demo.

stats_display() is the process target — it reads metric dicts from a
multiprocessing.Queue and re-renders the dashboard every second.
"""

import multiprocessing
import os
import queue as _queue_mod
import time
from datetime import datetime

_SEP = "=" * 48

_HOST_DEFAULTS: dict = {
    "video_tx_kbps": 0.0,
    "video_tx_fps":  0.0,
    "audio_tx_kbps": 0.0,
    "audio_tx_pps":  0.0,
    "input_rx_eps":  0.0,
}

_CLIENT_DEFAULTS: dict = {
    "video_rx_kbps":     0.0,
    "video_rx_pps":      0.0,
    "video_rx_loss_pct": 0.0,
    "audio_rx_kbps":     0.0,
    "audio_rx_pps":      0.0,
    "input_tx_eps":      0.0,
}


def _print_dashboard(state: dict, label: str, ts: str) -> None:
    """Render the dashboard to stdout. Called from stats_display only."""
    print(_SEP)
    print(f"  PIORSEC  |  {label:^6}  |  {ts}")
    print(_SEP)

    if label == "HOST":
        print(f"  [VIDEO TX]  {state['video_tx_kbps']:>8.0f} kbps   {state['video_tx_fps']:>5.1f} fps")
        print(f"  [AUDIO TX]  {state['audio_tx_kbps']:>8.0f} kbps   {state['audio_tx_pps']:>5.1f} pps")
        print(f"  [INPUT RX]  {state['input_rx_eps']:>8.1f} eps")
    else:
        loss = state['video_rx_loss_pct']
        print(f"  [VIDEO RX]  {state['video_rx_kbps']:>8.0f} kbps   {state['video_rx_pps']:>5.1f} pps   {loss:>4.1f}% loss")
        print(f"  [AUDIO RX]  {state['audio_rx_kbps']:>8.0f} kbps   {state['audio_rx_pps']:>5.1f} pps")
        print(f"  [INPUT TX]  {state['input_tx_eps']:>8.1f} eps")

    print(_SEP)
    print("  Ctrl+C to quit")


def stats_display(q: multiprocessing.Queue, mode: str) -> None:
    """Read stats from queue and render a live terminal dashboard every second.

    Parameters
    ----------
    q:    shared multiprocessing.Queue fed by worker processes
    mode: "host" or "client"
    """
    label = "HOST" if mode == "host" else "CLIENT"
    state = dict(_HOST_DEFAULTS if mode == "host" else _CLIENT_DEFAULTS)

    while True:
        time.sleep(1.0)

        # Drain all pending messages (non-blocking)
        while True:
            try:
                msg = q.get_nowait()
                state.update(msg)
            except _queue_mod.Empty:
                break

        os.system("cls" if os.name == "nt" else "clear")
        ts = datetime.now().strftime("%H:%M:%S")
        _print_dashboard(state, label, ts)
