# vision.py — Screen Capture & Visual Understanding (Llama 3.2 Vision)
"""
SON's eyes — captures the screen and sends images to the vision LLM.
Uses mss for fast screenshot capture and Ollama's Llama 3.2 Vision for analysis.
"""
import base64
import io
import time
from pathlib import Path

import config


class ScreenVision:
    """
    Screen capture and visual analysis using Llama 3.2 Vision via Ollama.
    """

    def __init__(self, brain=None):
        self._brain = brain
        self._screenshot_dir = Path(config.SCREENSHOT_DIR)
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)

    # ── Screenshot Capture ────────────────────────────────────

    def capture_screen(self, save_path: str | None = None, monitor: int = 0) -> str:
        """
        Capture the full screen (or specific monitor).

        Args:
            save_path: Optional path to save the screenshot.
            monitor: Monitor index (0 = all monitors, 1 = primary, etc.)

        Returns:
            Path to the saved screenshot file.
        """
        import mss
        from PIL import Image

        with mss.mss() as sct:
            monitors = sct.monitors
            mon = monitors[min(monitor, len(monitors) - 1)]
            screenshot = sct.grab(mon)

            # Convert to PIL Image
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        # Save
        if not save_path:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_path = str(self._screenshot_dir / f"screen_{timestamp}.png")

        img.save(save_path, "PNG")
        return save_path

    def capture_region(self, left: int, top: int, width: int, height: int,
                       save_path: str | None = None) -> str:
        """Capture a specific region of the screen."""
        import mss
        from PIL import Image

        region = {"left": left, "top": top, "width": width, "height": height}

        with mss.mss() as sct:
            screenshot = sct.grab(region)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        if not save_path:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_path = str(self._screenshot_dir / f"region_{timestamp}.png")

        img.save(save_path, "PNG")
        return save_path

    # ── Image Encoding ────────────────────────────────────────

    @staticmethod
    def image_to_base64(image_path: str) -> str:
        """Convert an image file to base64 string for Ollama."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    # ── Visual Analysis ───────────────────────────────────────

    def analyze_screen(self, question: str = "What is on my screen?") -> str:
        """
        Capture the screen and analyze it with the vision LLM.

        Args:
            question: What to ask about the screen contents.

        Returns:
            LLM's description/analysis of the screen.
        """
        screenshot_path = self.capture_screen()
        return self.analyze_image(screenshot_path, question)

    def analyze_image(self, image_path: str, question: str = "Describe this image.") -> str:
        """
        Analyze any image file using the vision model.

        Args:
            image_path: Path to the image file.
            question: What to ask about the image.

        Returns:
            LLM's analysis.
        """
        if not Path(image_path).exists():
            return f"Image not found: {image_path}"

        b64_image = self.image_to_base64(image_path)

        if self._brain:
            return self._brain.think_vision(question, images=[b64_image])

        # Fallback: direct Ollama call without Brain
        import ollama
        client = ollama.Client(host=config.OLLAMA_HOST)

        response = client.chat(
            model=config.VISION_MODEL,
            messages=[{
                "role": "user",
                "content": question,
                "images": [b64_image],
            }],
        )

        return response["message"]["content"]


# ═══════════════════════════════════════════════════════════
#  Tool Functions (for ToolRegistry)
# ═══════════════════════════════════════════════════════════

# Module-level instance (initialized when register_all is called)
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
