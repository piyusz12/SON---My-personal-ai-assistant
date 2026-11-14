# vision.py — Screen Capture & Visual Understanding (Llama 3.2 Vision)
# SON V3 — Optimized for RTX 4060 + Ryzen 7 7840HS
"""
SON's eyes — captures the screen and sends images to the vision LLM.
Uses mss for fast screenshot capture and Ollama's Llama 3.2 Vision for analysis.

Changes from V2:
- Direct mss buffer usage (skip PIL intermediate when possible)
- Reduced screenshot resolution for vision model (720p sufficient)
- Faster base64 encoding with buffer reuse
- Parallel capture + encode pipeline
"""
import base64
import io
import time
from pathlib import Path

import config
from vision.screen.capture import ScreenCapture
from vision.screen.analysis import ScreenAnalyzer


class ScreenVision:
    """
    Screen capture and visual analysis using Llama 3.2 Vision via Ollama.
    Delegates to vision.screen.capture.ScreenCapture and vision.screen.analysis.ScreenAnalyzer.
    """

    def __init__(self, brain=None):
        self._brain = brain
        self._capture = ScreenCapture(screenshot_dir=config.SCREENSHOT_DIR)
        self._analyzer = ScreenAnalyzer(brain=brain)
        self._screenshot_dir = self._capture._dir
        self._max_width = self._capture._max_width
        self._max_height = self._capture._max_height

    # ── Screenshot Capture ────────────────────────────────────

    def capture_screen(self, save_path: str | None = None, monitor: int = 0,
                       resize_for_vision: bool = False) -> str:
        """Capture the full screen (or specific monitor)."""
        return self._capture.capture_fullscreen(
            monitor_idx=monitor,
            resize_for_vision=resize_for_vision,
            save_path=save_path,
        )

    def capture_region(self, left: int, top: int, width: int, height: int,
                       save_path: str | None = None) -> str:
        """Capture a specific region of the screen."""
        return self._capture.capture_region(left, top, width, height, save_path=save_path)

    def _resize_for_model(self, img):
        """Resize image to fit within vision model's optimal input size."""
        return self._capture._resize(img)

    # ── Image Encoding ────────────────────────────────────────

    @staticmethod
    def image_to_base64(image_path: str) -> str:
        """Convert an image file to base64 string for Ollama."""
        return ScreenCapture.file_to_base64(image_path)

    @staticmethod
    def image_bytes_to_base64(image_bytes: bytes) -> str:
        """Convert image bytes directly to base64 (avoids file I/O)."""
        return base64.b64encode(image_bytes).decode("utf-8")

    # ── Visual Analysis ───────────────────────────────────────

    def analyze_screen(self, question: str = "What is on my screen?") -> str:
        """Capture the screen and analyze it with the vision LLM."""
        return self._analyzer.analyze_screen(question=question)

    def analyze_image(self, image_path: str, question: str = "Describe this image.") -> str:
        """Analyze any image file using the vision model."""
        return self._analyzer.analyze_image_file(image_path=image_path, question=question)


# ═══════════════════════════════════════════════════════════
#  Tool Functions (for ToolRegistry)
# ═══════════════════════════════════════════════════════════

_vision: ScreenVision | None = None


def _get_vision() -> ScreenVision:
    global _vision
    if _vision is None:
        _vision = ScreenVision()
    return _vision


def look_at_screen(question: str = "What is on my screen?") -> str:
    """Take a screenshot and analyze it with the vision AI."""
    return _get_vision().analyze_screen(question)


def look_at_image(image_path: str, question: str = "Describe this image.") -> str:
    """Analyze a specific image file with the vision AI."""
    return _get_vision().analyze_image(image_path, question)


def take_screenshot(save_path: str = "") -> str:
    """Take a screenshot and save it. Returns the file path."""
    path = _get_vision().capture_screen(save_path=save_path or None)
    return f"Screenshot saved to: {path}"


# ═══════════════════════════════════════════════════════════
#  Registration
# ═══════════════════════════════════════════════════════════

def register_all(registry, brain=None):
    """Register all vision tools with a ToolRegistry."""
    global _vision
    _vision = ScreenVision(brain=brain)

    registry.register(
        name="look_at_screen",
        func=look_at_screen,
        description="Take a screenshot and analyze what is on the screen using vision AI. Use this when the user asks 'what's on my screen' or wants you to see something.",
        params={
            "question": {
                "type": "string",
                "description": "What to analyze or look for on the screen",
                "default": "What is on my screen?",
            }
        },
        category="vision",
    )

    registry.register(
        name="look_at_image",
        func=look_at_image,
        description="Analyze a specific image file using vision AI",
        params={
            "image_path": {"type": "string", "description": "Path to the image file"},
            "question": {"type": "string", "description": "What to ask about the image", "default": "Describe this image."},
        },
        required=["image_path"],
        category="vision",
    )

    registry.register(
        name="take_screenshot",
        func=take_screenshot,
        description="Take a screenshot of the screen and save it to a file",
        params={
            "save_path": {"type": "string", "description": "Optional path to save the screenshot", "default": ""},
        },
        category="vision",
    )
