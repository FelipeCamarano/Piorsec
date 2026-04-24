"""
Audio capture process (Host side).

Captures system audio from the game using PyAudio with WASAPI loopback
interface (Windows). Raw PCM audio is compressed in real time using the
Opus codec before being sent to the client via UDP (port 5001).
"""
