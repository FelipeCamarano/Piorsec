"""
Screen capture process (Host side).

Uses MSS (Multiple ScreenShots) to capture frames from the game window
at high speed via ctypes. Captured raw frames are placed into shared
memory for zero-copy access by the encoder process.
"""
