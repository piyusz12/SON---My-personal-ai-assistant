# vision/camera/events.py — Event-Driven Vision Loop for SON V3
"""
Event-Based Vision Loop:
Runs lightweight person/motion detection at a low frequency (1-3 FPS).
Emits discrete episodic events (e.g. 'person_entered', 'person_left', 'known_person_detected')
into SQLite memory without wasting GPU compute on continuous vision model calls.
"""
import logging
import threading
import time
from typing import Callable, Any

from vision.camera.capture import CameraManager
from vision.camera.detection import PersonDetector
from vision.camera.recognition import FaceRecognizer
from memory.structured_memory import StructuredMemory


class VisionEventLoop:
    """
    Background event-driven vision processor.
    Monitors camera state at low CPU cost and fires events when state changes.
    """

    def __init__(
        self,
        camera_manager: CameraManager | None = None,
        structured_memory: StructuredMemory | None = None,
        on_event_callback: Callable[[str, dict[str, Any]], None] | None = None,
        poll_interval: float = 1.0,
    ):
        self.camera = camera_manager or CameraManager()
        self.memory = structured_memory or StructuredMemory()
        self.detector = PersonDetector()
        self.recognizer = FaceRecognizer(structured_memory=self.memory)
        self.on_event = on_event_callback
        self.poll_interval = poll_interval

        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # State tracking
        self._last_person_count = 0
        self._last_detected_names = set()

    def start(self):
        """Start the event loop thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._loop, daemon=True, name="son-vision-events")
            self._thread.start()

    def stop(self):
        """Stop the event loop."""
        with self._lock:
            self._running = False
            if self._thread:
                self._thread.join(timeout=2)
                self._thread = None

    def _loop(self):
        while self._running:
            try:
                # Check privacy settings
                privacy = self.camera.get_privacy_status()
                if not privacy["camera_active"] or not privacy["person_detection_enabled"]:
                    time.sleep(self.poll_interval)
                    continue

                frame = self.camera.get_frame()
                if frame is None:
                    time.sleep(self.poll_interval)
                    continue

                # 1. Person Detection Check
                detection = self.detector.detect(frame)
                current_count = detection.person_count

                # State change: Person entered
                if current_count > self._last_person_count:
                    event_data = {
                        "count": current_count,
                        "motion_score": detection.motion_score,
                    }
                    self.memory.log_event("person_entered", event_data)
                    if self.on_event:
                        self.on_event("person_entered", event_data)

                # State change: Person left
                elif current_count < self._last_person_count:
                    event_data = {
                        "count": current_count,
                    }
                    self.memory.log_event("person_left", event_data)
                    if self.on_event:
                        self.on_event("person_left", event_data)

                self._last_person_count = current_count

                # 2. Face Recognition Check (only if people present and feature enabled)
                if current_count > 0 and privacy["face_recognition_enabled"]:
                    matches = self.recognizer.recognize_frame(frame)
                    current_names = {m.display_name for m in matches if m.is_known}

                    new_recognitions = current_names - self._last_detected_names
                    for name in new_recognitions:
                        rec_data = {"name": name}
                        self.memory.log_event("known_person_detected", rec_data)
                        if self.on_event:
                            self.on_event("known_person_detected", rec_data)

                    self._last_detected_names = current_names
                else:
                    self._last_detected_names = set()

            except Exception:
                pass

            time.sleep(self.poll_interval)
