"""
Mock frame and event generators for the Piorsec pipeline demo.

All functions return data in the same format the real pipeline will use,
but with random bytes instead of actual encoded media.

Size references:
  P-frame  ~10 400 B   →  5 Mbps / 60 fps  ≈ 10 417 B
  I-frame  ~85 000 B   →  I-frame ≈ 8× P-frame (conservative)
  Audio      ~320 B    →  Opus 128 kbps stereo @ 20 ms
  Input        8 B     →  struct ">HBBi" (fixed, no payload)
"""

import random

import numpy as np

from piorsec.shared.protocol import EventType

# One RNG per process — each spawned process gets its own copy after fork/spawn,
# so there is no sharing or lock contention.
_rng = np.random.default_rng()

MOCK_P_FRAME_SIZE    = 10_400   # bytes — average compressed P-frame
MOCK_I_FRAME_SIZE    = 85_000   # bytes — compressed I-frame (keyframe)
MOCK_AUDIO_FRAME_SIZE =   320   # bytes — one Opus 20 ms frame

_ALL_EVENT_TYPES = [
    EventType.KEY_DOWN,
    EventType.KEY_UP,
    EventType.BTN_DOWN,
    EventType.BTN_UP,
    EventType.AXIS,
]


def mock_video_frame(is_keyframe: bool = False) -> bytes:
    """Return random bytes simulating a compressed video frame.

    is_keyframe=True returns an I-frame (~85 KB).
    is_keyframe=False returns a P-frame (~10 KB).
    """
    size = MOCK_I_FRAME_SIZE if is_keyframe else MOCK_P_FRAME_SIZE
    return _rng.bytes(size)


def mock_audio_frame() -> bytes:
    """Return 320 random bytes simulating one Opus audio frame (20 ms)."""
    return _rng.bytes(MOCK_AUDIO_FRAME_SIZE)


def mock_input_event() -> tuple[int, int]:
    """Return (event_type, value) for a random input event.

    Axis values are in [-32768, 32767] (signed 16-bit range).
    Key/button codes are in [0, 255].
    """
    event_type = random.choice(_ALL_EVENT_TYPES)
    if event_type == EventType.AXIS:
        value = random.randint(-32_768, 32_767)
    else:
        value = random.randint(0, 255)
    return event_type, value
