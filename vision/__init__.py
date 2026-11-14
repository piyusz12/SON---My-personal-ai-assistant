# vision/__init__.py — SON V3 Vision & Camera Subsystem
"""
SON V3 Vision System:
- Camera Vision: Person detection, local face recognition, motion check, privacy gate
- Screen Vision: Screenshot capture, UI understanding, OCR, error analysis
"""
from vision.screen.capture import ScreenCapture
from vision.screen.analysis import ScreenAnalyzer
from vision.screen.ocr import ScreenOCR

try:
    import vision as _v
    ScreenVision = getattr(_v, "ScreenVision", None)
    take_screenshot = getattr(_v, "take_screenshot", None)
    look_at_screen = getattr(_v, "look_at_screen", None)
    look_at_image = getattr(_v, "look_at_image", None)
except Exception:
    ScreenVision = None
    take_screenshot = None
    look_at_screen = None
    look_at_image = None

__all__ = [
    "ScreenCapture",
    "ScreenAnalyzer",
    "ScreenOCR",
    "ScreenVision",
    "take_screenshot",
    "look_at_screen",
    "look_at_image",
]
