"""
Piorsec — CLI entry point.

Usage:
  piorsec host   --client-ip <CLIENT_IP>   # run as host
  piorsec client --ip        <HOST_IP>     # run as client
"""

import argparse
import multiprocessing as mp


# ---------------------------------------------------------------------------
# Host mode
# ---------------------------------------------------------------------------
def run_host(client_ip: str) -> None:
    """Spawn all host processes and wait until Ctrl+C."""
    from piorsec.host.input_receiver import input_receiver
    from piorsec.host.sender import audio_sender, video_sender
    from piorsec.shared.stats import stats_display

    q = mp.Queue()
    procs = [
        mp.Process(target=video_sender,   args=(client_ip, q), name="video_sender",   daemon=True),
        mp.Process(target=audio_sender,   args=(client_ip, q), name="audio_sender",   daemon=True),
        mp.Process(target=input_receiver, args=(q,),           name="input_receiver", daemon=True),
        mp.Process(target=stats_display,  args=(q, "host"),    name="stats_display",  daemon=True),
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


# ---------------------------------------------------------------------------
# Client mode
# ---------------------------------------------------------------------------
def run_client(host_ip: str) -> None:
    """Spawn all client processes and wait until Ctrl+C."""
    from piorsec.client.input_sender import input_sender
    from piorsec.client.receiver import audio_receiver, video_receiver
    from piorsec.shared.stats import stats_display

    q = mp.Queue()
    procs = [
        mp.Process(target=video_receiver, args=(q,),          name="video_receiver", daemon=True),
        mp.Process(target=audio_receiver, args=(q,),          name="audio_receiver", daemon=True),
        mp.Process(target=input_sender,   args=(host_ip, q),  name="input_sender",   daemon=True),
        mp.Process(target=stats_display,  args=(q, "client"), name="stats_display",  daemon=True),
    ]
    for p in procs:
        p.start()

    print(f"[piorsec] CLIENT started — connected to {host_ip}. Press Ctrl+C to stop.")
    try:
        for p in procs:
            p.join()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()
        for p in procs:
            p.join(timeout=2)
        print("\n[piorsec] Client stopped.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        prog="piorsec",
        description="P2P game streaming — play local multiplayer games online.",
    )
    mode = parser.add_subparsers(dest="mode", required=True)

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
        run_host(args.client_ip)
    elif args.mode == "client":
        run_client(args.ip)


if __name__ == "__main__":
    mp.freeze_support()   # required for PyInstaller / Windows spawn
    main()
