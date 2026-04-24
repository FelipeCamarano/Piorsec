"""
Global configuration for the Piorsec streaming system.
"""

# Video
VIDEO_CODEC_PRIMARY  = "hevc"   # H.265 — primary, requires GPU (NVENC/AMF)
VIDEO_CODEC_FALLBACK = "h264"   # H.264 — fallback for older hardware
VIDEO_FPS            = 60
VIDEO_BITRATE        = 5_000_000  # 5 Mbps

# Audio
AUDIO_SAMPLE_RATE    = 48_000   # Hz — Opus optimal sample rate
AUDIO_CHANNELS       = 2        # stereo
AUDIO_CHUNK_SIZE     = 960      # samples per Opus frame (20ms at 48kHz)

# Network
UDP_BUFFER_SIZE      = 65_507   # max UDP payload (bytes)
