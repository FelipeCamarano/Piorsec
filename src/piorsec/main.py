"""
Piorsec — CLI/GUI entry point.

Usage:
  piorsec                          # launch GUI
  piorsec host   --client-ip <IP>  # run as host (CLI)
  piorsec client --ip        <IP>  # run as client (CLI)
"""

import argparse
import multiprocessing as mp
import sys


def _run_host_cli(client_ip: str) -> None:
    """Spawn all host processes and wait until Ctrl+C."""
    from piorsec.host.audio import audio_capture
    from piorsec.host.capture import screen_capture
    from piorsec.host.encoder import video_encoder
    from piorsec.host.input_receiver import input_receiver
    from piorsec.host.sender import audio_sender, video_sender
    from piorsec.shared.stats import stats_display

    raw_frame_queue = mp.Queue(maxsize=2)
    encoded_queue = mp.Queue(maxsize=64)
    audio_queue = mp.Queue(maxsize=64)
    stats_q = mp.Queue()

    procs = [
        mp.Process(target=screen_capture,  args=(raw_frame_queue,),               name="capture",        daemon=True),
        mp.Process(target=video_encoder,   args=(raw_frame_queue, encoded_queue, stats_q), name="encoder", daemon=True),
        mp.Process(target=video_sender,    args=(client_ip, encoded_queue, stats_q), name="video_sender", daemon=True),
        mp.Process(target=audio_capture,   args=(audio_queue, stats_q),            name="audio_capture", daemon=True),
        mp.Process(target=audio_sender,    args=(client_ip, audio_queue, stats_q),  name="audio_sender",  daemon=True),
        mp.Process(target=input_receiver,  args=(stats_q,),                        name="input_receiver", daemon=True),
        mp.Process(target=stats_display,   args=(stats_q, "host"),                  name="stats_display",  daemon=True),
    ]
    for p in procs:
        p.start()

    print(f"[piorsec] HOST started — streaming to {client_ip}. Press Ctrl+C to stop.")
    try:
        for p in procs:
            p.join()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()
        for p in procs:
            p.join(timeout=2)
        print("\n[piorsec] Host stopped.")


def _run_client_cli(host_ip: str) -> None:
    """Spawn all client processes and run the Qt GUI in the main thread."""
    from PySide6.QtWidgets import QApplication

    from piorsec.client.audio_output import audio_output
    from piorsec.client.decoder import video_decoder
    from piorsec.client.gui import MainWindow
    from piorsec.client.input_sender import input_sender
    from piorsec.client.receiver import audio_receiver, video_receiver

    app = QApplication(sys.argv)

    packet_queue = mp.Queue(maxsize=256)
    frame_queue = mp.Queue(maxsize=2)
    audio_queue = mp.Queue(maxsize=64)
    stats_queue = mp.Queue(maxsize=64)

    procs = [
        mp.Process(target=video_receiver, args=(packet_queue, stats_queue), name="video_receiver", daemon=True),
        mp.Process(target=video_decoder,  args=(packet_queue, frame_queue, stats_queue), name="video_decoder", daemon=True),
        mp.Process(target=audio_receiver, args=(audio_queue, stats_queue),  name="audio_receiver", daemon=True),
        mp.Process(target=audio_output,   args=(audio_queue, stats_queue),  name="audio_output",   daemon=True),
        mp.Process(target=input_sender,   args=(host_ip, stats_queue),      name="input_sender",   daemon=True),
    ]
    for p in procs:
        p.start()

    window = MainWindow(frame_queue, stats_queue)
    window.setWindowTitle(f"Piorsec — Client ({host_ip})")
    window.show()

    print(f"[piorsec] CLIENT started — connected to {host_ip}. Close window to stop.")

    try:
        app.exec()
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.join(timeout=2)
        print("\n[piorsec] Client stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="piorsec",
        description="P2P game streaming — play local multiplayer games online.",
    )
    mode = parser.add_subparsers(dest="mode")

    host_cmd = mode.add_parser("host", help="Host a game session (streams to a client).")
    host_cmd.add_argument(
        "--client-ip",
        required=True,
        metavar="CLIENT_IP",
        help="IP address of the client machine (or 127.0.0.1 for local testing).",
    )

    client_cmd = mode.add_parser("client", help="Join a hosted game session.")
    client_cmd.add_argument(
        "--ip",
        required=True,
        metavar="HOST_IP",
        help="Public IP (or VPN/LAN IP) of the host machine.",
    )

    args = parser.parse_args()

    if args.mode == "host":
        _run_host_cli(args.client_ip)
    elif args.mode == "client":
        _run_client_cli(args.ip)
    else:
        # No subcommand — launch GUI
        from piorsec.gui.launcher import run_launcher
        run_launcher()


if __name__ == "__main__":
    mp.freeze_support()   # required for PyInstaller / Windows spawn
    main()
