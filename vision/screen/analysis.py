# vision/screen/analysis.py — Screen Visual Analysis (Llama 3.2 Vision) for SON V3
"""
Performs visual inspection of screenshots using the Vision LLM (llama3.2-vision).
Answers questions like:
- "What's on my screen?"
- "What is this error?"
- "Read this document on screen."
- "What's wrong with this UI?"
"""
from pathlib import Path
from vision.screen.capture import ScreenCapture
from core.config import Config


class ScreenAnalyzer:
    """
    Orchestrates screenshot capture and visual inference with the Vision LLM.
    """

    def __init__(self, brain=None):
        self.brain = brain
        self.capture = ScreenCapture()

    def analyze_screen(self, question: str = "Describe what you see on the screen in detail.") -> str:
        """Capture screen and run visual analysis."""
        screenshot_path = self.capture.capture_fullscreen(resize_for_vision=True)
        return self.analyze_image_file(screenshot_path, question)

    def analyze_image_file(self, image_path: str, question: str = "Describe this image.") -> str:
        """Run vision model on an existing image file."""
        if not Path(image_path).exists():
            return f"Image file not found: {image_path}"

        b64_image = self.capture.file_to_base64(image_path)

        if self.brain and hasattr(self.brain, "think_vision"):
            return self.brain.think_vision(question, images=[b64_image])

        # Direct Ollama fallback
        try:
            import ollama
            client = ollama.Client(host=Config.OLLAMA_HOST)
            response = client.chat(
                model=Config.VISION_MODEL,
                messages=[{
                    "role": "user",
                    "content": question,
                    "images": [b64_image],
                }],
            )
            return response["message"]["content"]
        except Exception as e:
            return f"Vision model inference failed: {e}"
