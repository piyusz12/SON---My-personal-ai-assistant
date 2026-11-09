# vision/__init__.py — SON V3 Vision & Camera Subsystem
"""
SON V3 Vision System:
- Camera Vision: Person detection, local face recognition, motion check, privacy gate
- Screen Vision: Screenshot capture, UI understanding, OCR, error analysis
"""
try:
    import importlib.util
    from pathlib import Path
    _root_vision = Path(__file__).resolve().parent.parent / "vision.py"
    if _root_vision.exists():
        _spec = importlib.util.spec_from_file_location("vision_root", str(_root_vision))
        if _spec and _spec.loader:
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            ScreenVision = getattr(_mod, "ScreenVision", None)
            take_screenshot = getattr(_mod, "take_screenshot", None)
except Exception:
    ScreenVision = None
