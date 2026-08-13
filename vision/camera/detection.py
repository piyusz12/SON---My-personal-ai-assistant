# vision/camera/detection.py — Person Detection & Motion Check for SON V3
"""
Person Detection (Detection vs Identification):
This module detects the presence and count of human bodies/motion in the room.
It does NOT identify who the person is.

Capabilities:
- is_person_present(frame) -> bool
- count_people(frame) -> int
- check_motion(frame) -> float
- format_room_status() -> str (e.g. "I detect 1 person in the room.")
"""
from dataclasses import dataclass
from typing import Any
import numpy as np

try:
    import cv2
    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False


@dataclass
class DetectionResult:
    person_present: bool
    person_count: int
    motion_score: float
    bounding_boxes: list[tuple[int, int, int, int]]  # (x, y, w, h)


class PersonDetector:
    """
    Lightweight human body & motion detector using HOG + Upper-body/Face Cascades.
    """

    def __init__(self):
        self._hog = None
        self._cascade = None
        self._prev_gray = None

        if _HAS_CV2:
            try:
                # 1. HOG People Detector
                self._hog = cv2.HOGDescriptor()
                self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            except Exception:
                self._hog = None

            try:
                # 2. Upper Body / Face Cascade fallback
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                self._cascade = cv2.CascadeClassifier(cascade_path)
            except Exception:
                self._cascade = None

    def check_motion(self, frame: np.ndarray) -> float:
        """
        Calculate motion score (0.0 to 1.0) compared to previous frame.
        """
        if not _HAS_CV2 or frame is None:
            return 0.0

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self._prev_gray is None:
            self._prev_gray = gray
            return 0.0

        frame_delta = cv2.absdiff(self._prev_gray, gray)
        self._prev_gray = gray

        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        motion_ratio = np.count_nonzero(thresh) / thresh.size
        return float(min(1.0, motion_ratio * 10))

    def detect(self, frame: np.ndarray) -> DetectionResult:
        """
        Detect human bodies / faces in the given frame.
        """
        if not _HAS_CV2 or frame is None:
            return DetectionResult(person_present=False, person_count=0, motion_score=0.0, bounding_boxes=[])

        motion = self.check_motion(frame)
        boxes: list[tuple[int, int, int, int]] = []

        # 1. Try Cascade detector on resized frame for speed
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self._cascade and not self._cascade.empty():
            faces = self._cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(30, 30),
            )
            for (x, y, w, h) in faces:
                boxes.append((int(x), int(y), int(w), int(h)))

        # 2. If no faces found, check HOG people detector
        if not boxes and self._hog:
            try:
                rects, weights = self._hog.detectMultiScale(
                    frame,
                    winStride=(8, 8),
                    padding=(4, 4),
                    scale=1.05,
                )
                for (x, y, w, h) in rects:
                    boxes.append((int(x), int(y), int(w), int(h)))
            except Exception:
                pass

        count = len(boxes)
        present = count > 0

        return DetectionResult(
            person_present=present,
            person_count=count,
            motion_score=motion,
            bounding_boxes=boxes,
        )

    def is_anyone_present(self, frame: np.ndarray | None) -> tuple[bool, str]:
        """
        Human-friendly response generator for: 'Is anyone in the room?'
        """
        if frame is None:
            return False, "Camera is currently unavailable or paused for privacy."

        result = self.detect(frame)
        if result.person_count == 1:
            return True, "Yes, I detect one person in the room."
        elif result.person_count > 1:
            return True, f"Yes, I detect {result.person_count} people in the room."
        else:
            if result.motion_score > 0.3:
                return False, "I don't clearly see a person, but there is motion in the room."
            return False, "No, nobody is detected in the room right now."
