# vision/screen/capture.py — Desktop Screen & Region Capture for SON V3
"""
High-performance screen grabber using mss.
Supports full-screen, specific monitors, downscaled frames for VRAM optimization,
and custom bounding regions.
"""
import base64
import time
from pathlib import Path
from typing import Any
from PIL import Image

import mss
from core.config import Config


class ScreenCapture:
    """
    Fast screen capture using mss with downscale optimization for vision LLMs.
    """

    def __init__(self, screenshot_dir: str | Path | None = None):
        self._dir = Path(screenshot_dir or Config.SCREENSHOTS_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._max_width = 1280
        self._max_height = 720

    def capture_fullscreen(self, monitor_idx: int = 1, resize_for_vision: bool = True, save_path: str | None = None) -> str:
        """
        Capture the desktop screen and return the file path.
        Uses mss with PIL ImageGrab fallback.
        """
        try:
            with mss.mss() as sct:
                monitors = sct.monitors
                idx = min(monitor_idx, len(monitors) - 1)
                mon = monitors[idx]
                shot = sct.grab(mon)
                img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        except Exception:
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab()
            except Exception:
                # Headless/virtual display fallback
                img = Image.new("RGB", (1280, 720), color=(30, 30, 30))

        if resize_for_vision:
            img = self._resize(img)

        if not save_path:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            ext = "jpg" if resize_for_vision else "png"
            save_path = str(self._dir / f"screen_{timestamp}.{ext}")

        if resize_for_vision:
            img.save(save_path, "JPEG", quality=85)
        else:
            img.save(save_path, "PNG")

        return save_path

    def capture_region(self, left: int, top: int, width: int, height: int, save_path: str | None = None) -> str:
        """Capture a specific bounding box on the screen."""
        with mss.mss() as sct:
            region = {"left": left, "top": top, "width": width, "height": height}
            shot = sct.grab(region)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

        if not save_path:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_path = str(self._dir / f"region_{timestamp}.png")

        img.save(save_path, "PNG")
        return save_path

    def _resize(self, img: Image.Image) -> Image.Image:
        w, h = img.size
        if w <= self._max_width and h <= self._max_height:
            return img
        ratio = min(self._max_width / w, self._max_height / h)
        new_size = (int(w * ratio), int(h * ratio))
        return img.resize(new_size, resample=Image.Resampling.LANCZOS)

    @staticmethod
    def file_to_base64(filepath: str) -> str:
        with open(filepath, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
