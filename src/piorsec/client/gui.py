"""
Main GUI window for the Piorsec client.

Contains the video viewport and a live status panel.  Runs in the main
(process) thread alongside the Qt event loop.
"""

import multiprocessing
import queue

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from piorsec.client.display import VideoWidget


class MainWindow(QMainWindow):
    """Client main window: video + live stats."""

    def __init__(
        self,
        frame_queue: multiprocessing.Queue,
        stats_queue: multiprocessing.Queue,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Piorsec — Client")
        self.resize(1280, 720)

        self._frame_queue = frame_queue
        self._stats_queue = stats_queue

        # Central widget layout
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Video viewport
        self._video = VideoWidget()
        layout.addWidget(self._video, stretch=1)

        # Status panel
        self._status_panel = QWidget()
        self._status_panel.setFixedWidth(220)
        status_layout = QVBoxLayout(self._status_panel)
        status_layout.setSpacing(8)

        self._lbl_conn = QLabel("Connection: waiting…")
        self._lbl_video_rx = QLabel("Video RX: —")
        self._lbl_decoder = QLabel("Decoder: —")
        self._lbl_audio_rx = QLabel("Audio RX: —")
        self._lbl_input_tx = QLabel("Input TX: —")

        for lbl in (
            self._lbl_conn,
            self._lbl_video_rx,
            self._lbl_decoder,
            self._lbl_audio_rx,
            self._lbl_input_tx,
        ):
            status_layout.addWidget(lbl)

        status_layout.addStretch()
        layout.addWidget(self._status_panel)

        # Stats accumulator
        self._stats_state: dict = {
            "video_rx_kbps": 0.0,
            "video_rx_pps": 0.0,
            "video_rx_loss_pct": 0.0,
            "audio_rx_kbps": 0.0,
            "audio_rx_pps": 0.0,
            "input_tx_eps": 0.0,
            "decoder_fps": 0.0,
        }

        # Timers
        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._poll_frame)
        self._frame_timer.start(16)  # ~60 Hz

        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._poll_stats)
        self._stats_timer.start(250)  # 4× per second for smooth UI

    # ------------------------------------------------------------------
    # Frame polling
    # ------------------------------------------------------------------
    def _poll_frame(self) -> None:
        """Grab the most recent decoded frame and display it."""
        latest = None
        while True:
            try:
                latest = self._frame_queue.get_nowait()
            except Exception:
                break
        if latest is not None:
            self._video.set_frame(latest)
            self._lbl_conn.setText("Connection: connected")

    # ------------------------------------------------------------------
    # Stats polling
    # ------------------------------------------------------------------
    def _poll_stats(self) -> None:
        """Drain stats queue and update labels."""
        while True:
            try:
                msg = self._stats_queue.get_nowait()
                self._stats_state.update(msg)
            except Exception:
                break

        s = self._stats_state
        self._lbl_video_rx.setText(
            f"Video RX: {s['video_rx_kbps']:>7.0f} kbps  "
            f"{s['video_rx_pps']:>5.1f} pps  "
            f"{s['video_rx_loss_pct']:>4.1f}% loss"
        )
        self._lbl_decoder.setText(
            f"Decoder:  {s['decoder_fps']:>7.1f} fps"
        )
        self._lbl_audio_rx.setText(
            f"Audio RX: {s['audio_rx_kbps']:>7.0f} kbps  "
            f"{s['audio_rx_pps']:>5.1f} pps"
        )
        self._lbl_input_tx.setText(
            f"Input TX: {s['input_tx_eps']:>7.1f} eps"
        )
