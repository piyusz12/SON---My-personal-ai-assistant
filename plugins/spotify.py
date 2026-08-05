from core.config import SecurityLevel
from plugins.base import BasePlugin


class SpotifyPlugin(BasePlugin):
    """
    Controls Spotify playback using Windows media key simulation / Spotify URI calls.
    """

    def __init__(self):
        super().__init__(name="spotify", description="Spotify media player controller", category="media")

    def initialize(self):
        self.register_tool(
            "spotify_play_pause", self.play_pause,
            description="Toggle Spotify play / pause state",
            params={}, security_level=SecurityLevel.SAFE
        )
        self.register_tool(
            "spotify_next_track", self.next_track,
            description="Skip to next Spotify track",
            params={}, security_level=SecurityLevel.SAFE
        )
        self.register_tool(
            "spotify_previous_track", self.previous_track,
            description="Skip to previous Spotify track",
            params={}, security_level=SecurityLevel.SAFE
        )

    def _send_media_key(self, key_code: int):
        import ctypes
        # VK_MEDIA_NEXT_TRACK = 0xB0, VK_MEDIA_PREV_TRACK = 0xB1, VK_MEDIA_PLAY_PAUSE = 0xB3
        ctypes.windll.user32.keybd_event(key_code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(key_code, 0, 2, 0)  # KEYEVENTF_KEYUP = 2

    def play_pause(self) -> str:
        self._send_media_key(0xB3)
        return "Toggled Spotify Play/Pause."

    def next_track(self) -> str:
        self._send_media_key(0xB0)
        return "Skipped to next track."

    def previous_track(self) -> str:
        self._send_media_key(0xB1)
        return "Skipped to previous track."
