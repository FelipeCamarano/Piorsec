"""
Protocol constants shared between host and client.
"""

import struct

# UDP ports — one per stream for easier debugging and port forwarding
VIDEO_PORT = 5000   # Host → Client (H.265/H.264 via RTP)
AUDIO_PORT = 5001   # Host → Client (Opus)
INPUT_PORT = 5002   # Client → Host (input events)


# ---------------------------------------------------------------------------
# Input event types
# ---------------------------------------------------------------------------
class EventType:
    KEY_DOWN = 0x01
    KEY_UP   = 0x02
    BTN_DOWN = 0x03
    BTN_UP   = 0x04
    AXIS     = 0x05


# ---------------------------------------------------------------------------
# Payload type identifiers (carried in packet header)
# ---------------------------------------------------------------------------
class PayloadType:
    VIDEO_H265 = 0x60
    VIDEO_H264 = 0x61
    AUDIO_OPUS = 0x6B


# ---------------------------------------------------------------------------
# Binary packet formats (big-endian network byte order)
#
#   VIDEO_HEADER  ">BBHIHH"  →  12 bytes
#     version(B) | payload_type(B) | seq_num(H) | timestamp_ms(I)
#     | frag_index(H) | total_frags(H)
#
#   AUDIO_HEADER  ">BBHI"   →   8 bytes
#     version(B) | payload_type(B) | seq_num(H) | timestamp_ms(I)
#
#   INPUT_PACKET  ">HBBi"   →   8 bytes  (no separate payload)
#     session_id(H) | player_id(B) | event_type(B) | value(i signed int)
# ---------------------------------------------------------------------------
_VIDEO_HEADER_FMT = ">BBHIHH"
_AUDIO_HEADER_FMT = ">BBHI"
_INPUT_PACKET_FMT = ">HBBi"

VIDEO_HEADER_SIZE = struct.calcsize(_VIDEO_HEADER_FMT)   # 12
AUDIO_HEADER_SIZE = struct.calcsize(_AUDIO_HEADER_FMT)   # 8
INPUT_PACKET_SIZE = struct.calcsize(_INPUT_PACKET_FMT)   # 8


# ---------------------------------------------------------------------------
# Pack / unpack helpers
# ---------------------------------------------------------------------------
def pack_video(
    seq_num: int,
    timestamp_ms: int,
    frag_index: int,
    total_frags: int,
    payload: bytes,
    payload_type: int = PayloadType.VIDEO_H265,
    version: int = 1,
) -> bytes:
    """Return 12-byte header + payload as a single bytes object."""
    header = struct.pack(
        _VIDEO_HEADER_FMT,
        version, payload_type, seq_num, timestamp_ms, frag_index, total_frags,
    )
    return header + payload


def unpack_video(data: bytes) -> tuple:
    """Return (version, payload_type, seq_num, timestamp_ms, frag_index, total_frags, payload)."""
    fields = struct.unpack(_VIDEO_HEADER_FMT, data[:VIDEO_HEADER_SIZE])
    return fields + (data[VIDEO_HEADER_SIZE:],)


def pack_audio(
    seq_num: int,
    timestamp_ms: int,
    payload: bytes,
    payload_type: int = PayloadType.AUDIO_OPUS,
    version: int = 1,
) -> bytes:
    """Return 8-byte header + payload as a single bytes object."""
    header = struct.pack(_AUDIO_HEADER_FMT, version, payload_type, seq_num, timestamp_ms)
    return header + payload


def unpack_audio(data: bytes) -> tuple:
    """Return (version, payload_type, seq_num, timestamp_ms, payload)."""
    fields = struct.unpack(_AUDIO_HEADER_FMT, data[:AUDIO_HEADER_SIZE])
    return fields + (data[AUDIO_HEADER_SIZE:],)


def pack_input(session_id: int, player_id: int, event_type: int, value: int) -> bytes:
    """Return 8-byte input packet (no separate payload)."""
    return struct.pack(_INPUT_PACKET_FMT, session_id, player_id, event_type, value)


def unpack_input(data: bytes) -> tuple:
    """Return (session_id, player_id, event_type, value)."""
    return struct.unpack(_INPUT_PACKET_FMT, data[:INPUT_PACKET_SIZE])
