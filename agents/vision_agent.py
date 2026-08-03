# agents/vision_agent.py — Screen Vision Agent for SON V3
from vision import ScreenVision


class VisionAgent:
    """
    Coordinates screen captures and visual analysis using Llama 3.2 Vision.
    """

    def __init__(self, brain=None):
        self._vision = ScreenVision(brain=brain)

    def analyze_screen(self, question: str = "What is on my screen?") -> str:
        return self._vision.analyze_screen(question)

    def analyze_image(self, image_path: str, question: str = "Describe this image.") -> str:
        return self._vision.analyze_image(image_path, question)

    def take_screenshot(self, save_path: str = None) -> str:
        path = self._vision.capture_screen(save_path=save_path)
        return f"Screenshot saved to: {path}"
