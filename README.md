# Piorsec

> P2P online multiplayer for games originally designed for local co-op.

Streams the host's screen and audio to remote players in real time, while forwarding their keyboard and gamepad inputs back — no game modification required.

---

## How it works

```
HOST                                    CLIENT
  Game running locally
       │
       ├─ Screen capture (MSS)
       ├─ Video encode  (H.265/H.264) ──────────► UDP :5000 ──► decode ──► display
       ├─ Audio capture (WASAPI)
       └─ Audio encode  (Opus)        ──────────► UDP :5001 ──► decode ──► playback
                                      
       └─ Input inject (vgamepad)     ◄────────── UDP :5002 ◄── capture (pynput)
```

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)

## Installation

**1. Clone the repository:**

```bash
git clone <repo-url>
cd Piorsec
```

**2. Run the setup script for your platform:**

```bash
# Linux / macOS
bash setup.sh

# Windows (PowerShell)
.\setup.ps1
```

The script installs system dependencies (e.g. PortAudio for PyAudio), uv, and all Python packages via `uv sync` — one command and you're done.

## Usage

**Host** (the machine running the game):
```bash
uv run piorsec host --client-ip <CLIENT_IP>
```

**Client** (the remote player):
```bash
uv run piorsec client --ip <HOST_IP>
```

> For local testing, use `127.0.0.1` as the IP on both sides.

### Connecting over the internet

| Scenario | Solution |
|---|---|
| Host has public IP | Forward UDP ports 5000–5002 on your router |
| Host behind CGNAT | Use a VPN overlay (Radmin VPN, Tailscale, ZeroTier) |
| Same local network | Use the host's local IP directly |

## Project structure

```
src/piorsec/
├── main.py               # CLI entry point
├── host/
│   ├── capture.py        # Screen capture (MSS)
│   ├── encoder.py        # Video encoding (PyAV / H.265)
│   ├── audio.py          # Audio capture (PyAudio + WASAPI)
│   ├── sender.py         # UDP video + audio transmission
│   └── input_receiver.py # UDP input reception + injection
├── client/
│   ├── receiver.py       # UDP video + audio reception
│   ├── decoder.py        # Video decoding (PyAV)
│   ├── display.py        # Frame rendering (PySide6)
│   ├── audio_output.py   # Audio playback
│   └── input_sender.py   # Input capture + UDP transmission
└── shared/
    ├── protocol.py       # Binary packet definitions
    ├── config.py         # Global settings
    ├── mock.py           # Mock data generators
    └── stats.py          # Live stats dashboard
```

## License

MIT
