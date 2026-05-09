"""
Piorsec Launcher GUI.

A simple PySide6 window that lets the user choose between Host or Client mode,
enter the target IP, and start the session.
"""

import multiprocessing as mp
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from piorsec.client.audio_output import audio_output
from piorsec.client.decoder import video_decoder
from piorsec.client.gui import MainWindow as ClientMainWindow
from piorsec.client.input_sender import input_sender
from piorsec.client.receiver import audio_receiver, video_receiver
from piorsec.host.audio import audio_capture
from piorsec.host.capture import screen_capture
from piorsec.host.encoder import video_encoder
from piorsec.host.input_receiver import input_receiver
from piorsec.host.sender import audio_sender, video_sender


class LauncherWindow(QMainWindow):
    """Main launcher window for Piorsec."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Piorsec — Launcher")
        self.setFixedSize(420, 280)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel("Piorsec")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setPointSize(24)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        subtitle = QLabel("P2P Online Multiplayer Streaming")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # Mode selection
        mode_layout = QHBoxLayout()
        self._radio_host = QRadioButton("Host (stream my screen)")
        self._radio_client = QRadioButton("Client (join a session)")
        self._radio_client.setChecked(True)
        mode_layout.addWidget(self._radio_host)
        mode_layout.addWidget(self._radio_client)
        layout.addLayout(mode_layout)

        # IP input
        ip_layout = QHBoxLayout()
        ip_layout.addWidget(QLabel("IP Address:"))
        self._ip_input = QLineEdit()
        self._ip_input.setPlaceholderText("127.0.0.1")
        self._ip_input.setText("127.0.0.1")
        ip_layout.addWidget(self._ip_input)
        layout.addLayout(ip_layout)

        layout.addStretch()

        # Start button
        self._btn_start = QPushButton("Start")
        self._btn_start.setMinimumHeight(40)
        self._btn_start.clicked.connect(self._on_start)
        layout.addWidget(self._btn_start)

        self._procs: list[mp.Process] = []

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_start(self) -> None:
        ip = self._ip_input.text().strip()
        if not ip:
            QMessageBox.warning(self, "Missing IP", "Please enter an IP address.")
            return

        self._btn_start.setEnabled(False)
        self._btn_start.setText("Running…")

        if self._radio_host.isChecked():
            self._start_host(ip)
        else:
            self._start_client(ip)

    def _start_host(self, client_ip: str) -> None:
        """Spawn host processes and show a minimal status window."""
        raw_frame_queue = mp.Queue(maxsize=2)
        encoded_queue = mp.Queue(maxsize=64)
        audio_queue = mp.Queue(maxsize=64)
        stats_queue = mp.Queue(maxsize=64)

        self._procs = [
            mp.Process(target=screen_capture, args=(raw_frame_queue,), name="capture", daemon=True),
            mp.Process(target=video_encoder, args=(raw_frame_queue, encoded_queue, stats_queue), name="encoder", daemon=True),
            mp.Process(target=video_sender, args=(client_ip, encoded_queue, stats_queue), name="video_sender", daemon=True),
            mp.Process(target=audio_capture, args=(audio_queue, stats_queue), name="audio_capture", daemon=True),
            mp.Process(target=audio_sender, args=(client_ip, audio_queue, stats_queue), name="audio_sender", daemon=True),
            mp.Process(target=input_receiver, args=(stats_queue,), name="input_receiver", daemon=True),
        ]
        for p in self._procs:
            p.start()

        self._status_win = _StatusWindow("HOST", stats_queue, self._procs)
        self._status_win.destroyed.connect(self.close)
        self._status_win.show()
        self.hide()

    def _start_client(self, host_ip: str) -> None:
        """Spawn client processes and open the main client window."""
        packet_queue = mp.Queue(maxsize=256)
        frame_queue = mp.Queue(maxsize=2)
        audio_queue = mp.Queue(maxsize=64)
        stats_queue = mp.Queue(maxsize=64)

        self._procs = [
            mp.Process(target=video_receiver, args=(packet_queue, stats_queue), name="video_receiver", daemon=True),
            mp.Process(target=video_decoder, args=(packet_queue, frame_queue, stats_queue), name="video_decoder", daemon=True),
            mp.Process(target=audio_receiver, args=(audio_queue, stats_queue), name="audio_receiver", daemon=True),
            mp.Process(target=audio_output, args=(audio_queue, stats_queue), name="audio_output", daemon=True),
            mp.Process(target=input_sender, args=(host_ip, stats_queue), name="input_sender", daemon=True),
        ]
        for p in self._procs:
            p.start()

        self._client_win = ClientMainWindow(frame_queue, stats_queue)
        self._client_win.setWindowTitle(f"Piorsec — Client ({host_ip})")
        self._client_win.show()
        self.hide()

        # Terminate processes and close launcher when client window closes
        self._client_win.destroyed.connect(self._terminate_procs)
        self._client_win.destroyed.connect(self.close)

    def _terminate_procs(self) -> None:
        for p in self._procs:
            if p.is_alive():
                p.terminate()
        for p in self._procs:
            p.join(timeout=2)
        self.close()


class _StatusWindow(QMainWindow):
    """Minimal status window for the host mode."""

    def __init__(self, label: str, stats_queue: mp.Queue, procs: list[mp.Process]) -> None:
        super().__init__()
        self.setWindowTitle(f"Piorsec — {label}")
        self.setFixedSize(400, 200)
        self._procs = procs

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self._lbl = QLabel(f"{label} mode running…\n\nClose this window to stop.")
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._lbl)

        self._stats_queue = stats_queue
        self._state: dict = {}

        from PySide6.QtCore import QTimer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_stats)
        self._timer.start(500)

    def _poll_stats(self) -> None:
        while True:
            try:
                msg = self._stats_queue.get_nowait()
                self._state.update(msg)
            except Exception:
                break

        lines = [
            f"Video TX: {self._state.get('video_tx_kbps', 0):.0f} kbps  {self._state.get('video_tx_fps', 0):.1f} fps",
            f"Audio TX: {self._state.get('audio_tx_kbps', 0):.0f} kbps  {self._state.get('audio_tx_pps', 0):.1f} pps",
            f"Input RX: {self._state.get('input_rx_eps', 0):.1f} eps",
        ]
        self._lbl.setText("HOST mode running…\n\n" + "\n".join(lines) + "\n\nClose this window to stop.")

    def closeEvent(self, event) -> None:
        for p in self._procs:
            if p.is_alive():
                p.terminate()
        for p in self._procs:
            p.join(timeout=2)
        event.accept()


def run_launcher() -> None:
    """Entry point for the GUI launcher."""
    app = QApplication(sys.argv)
    win = LauncherWindow()
    win.show()
    sys.exit(app.exec())
