"""
Video encoding process (Host side).

Reads raw frames from shared memory and encodes them using PyAV (FFmpeg).
Primary codec: H.265/HEVC with GPU acceleration (NVENC/AMF).
Fallback codec: H.264/AVC for older hardware.
Encoded frames are packetized via RTP and handed to sender.py.
"""
