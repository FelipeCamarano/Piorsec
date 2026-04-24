# Piorsec — Architecture

P2P online multiplayer system for locally-multiplayer games (Rayman Legends/Origins).
Streams the host's screen and audio to remote clients while forwarding their inputs back.

## Overview

```
[HOST]                                      [CLIENT]
 Game
  │
  ├── MSS capture ──► shared memory
  │                        │
  │                   PyAV encode (H.265/H.264)
  │                        │
  │                   RTP packetize ──────────────────► UDP :5000 ──► decode ──► PySide6 display
  │
  ├── PyAudio + WASAPI loopback
  │        │
  │      Opus encode ─────────────────────────────────► UDP :5001 ──► Opus decode ──► PyAudio playback
  │
  └── vgamepad / ctypes SendInput ◄────────────────── UDP :5002 ◄── pynput capture
```

## Roles

### Host
- Runs the game locally
- Captures screen (MSS) and audio (PyAudio + WASAPI loopback)
- Encodes video with PyAV: H.265/HEVC primary (GPU: NVENC/AMF), H.264/AVC fallback
- Compresses audio with Opus codec
- Transmits via UDP using RTP packetization
- Receives input packets from client and injects them via vgamepad (gamepad) or ctypes SendInput (keyboard/mouse)

### Client
- Receives video and audio streams from host
- Decodes and displays video via PySide6
- Plays back audio via PyAudio
- Captures local inputs (pynput) and sends them to host

## Ports

| Stream | Port | Direction        | Protocol        |
|--------|------|------------------|-----------------|
| Video  | 5000 | Host → Client    | UDP / RTP       |
| Audio  | 5001 | Host → Client    | UDP             |
| Input  | 5002 | Client → Host    | UDP             |

## Connectivity

| Scenario                  | Solution                                      |
|---------------------------|-----------------------------------------------|
| Host has public IP        | Port forward UDP 5000–5002 on router          |
| Host behind CGNAT         | VPN overlay (Radmin / Tailscale / ZeroTier)   |
| Same LAN                  | Use local IP directly, no forwarding needed   |

The code is network-agnostic — only the IP the client connects to changes.

## Concurrency (Host)

Python's GIL prevents true thread parallelism for CPU-bound work.
The host uses **multiprocessing** with **shared memory (zero-copy)** to isolate:

| Process           | Responsibility                          |
|-------------------|-----------------------------------------|
| `capture`         | MSS screen capture → shared memory     |
| `encoder`         | Read shared memory → PyAV encode → RTP |
| `audio`           | PyAudio capture → Opus encode → send   |
| `input_receiver`  | Receive UDP inputs → inject into game  |

## Input Packet Format

```
| session_id (2B) | player_id (1B) | event_type (1B) | value (4B) |
```

Event types defined in `src/piorsec/shared/protocol.py`.

## Module Structure

```
src/piorsec/
├── main.py                  # CLI entry point (host / client --ip)
├── host/
│   ├── capture.py           # MSS screen capture process
│   ├── encoder.py           # PyAV H.265/H.264 encoding via RTP
│   ├── audio.py             # PyAudio + WASAPI + Opus capture
│   ├── sender.py            # UDP transmission (video :5000, audio :5001)
│   └── input_receiver.py    # UDP recv :5002 + vgamepad/SendInput injection
├── client/
│   ├── receiver.py          # UDP recv video/audio, RTP reassembly
│   ├── decoder.py           # PyAV decoding
│   ├── display.py           # PySide6 frame rendering
│   ├── audio_output.py      # Opus decode + PyAudio playback
│   └── input_sender.py      # pynput capture + UDP send :5002
└── shared/
    ├── protocol.py          # Port constants, event types
    └── config.py            # Codec settings, FPS, bitrate, buffer sizes
```

## Dependencies

| Library    | Purpose                                      |
|------------|----------------------------------------------|
| `mss`      | Ultra-fast screen capture via ctypes         |
| `av`       | PyAV — FFmpeg bindings for encode/decode/RTP |
| `pyaudio`  | Audio capture (WASAPI loopback) and playback |
| `pynput`   | Keyboard/mouse event capture (client)        |
| `vgamepad` | Virtual Xbox360/DS4 controller (host)        |
| `PySide6`  | Video rendering + future GUI                 |
| `numpy`    | Frame buffer manipulation (shared memory)    |
