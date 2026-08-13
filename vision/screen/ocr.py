# vision/screen/ocr.py — Screen Text & OCR Module for SON V3
"""
Lightweight OCR & text inspection module for screen regions.
"""
from pathlib import Path


class ScreenOCR:
    """
    Handles local OCR extraction for screen regions.
    """

    def __init__(self):
        self._tesseract_available = False
        try:
            import pytesseract
            self._pytesseract = pytesseract
            self._tesseract_available = True
        except ImportError:
            self._pytesseract = None

    def extract_text(self, image_path: str) -> str:
        """Extract text from an image file."""
        if not self._tesseract_available:
            return "OCR library (pytesseract) is not installed. Use vision model for text analysis."

        try:
            from PIL import Image
            img = Image.open(image_path)
            text = self._pytesseract.image_to_string(img)
            return text.strip() or "No readable text detected in the image."
        except Exception as e:
            return f"OCR extraction failed: {e}"
