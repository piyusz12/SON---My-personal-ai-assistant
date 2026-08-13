# vision/camera/capture.py — Camera Capture & Privacy Gate for SON V3
"""
Manages camera device access with strict privacy controls.
Features:
- Thread-safe background frame grabber
- Hard privacy pause/stop (physically releases or halts camera stream)
- Privacy flags: Camera Active, Person Detection Enabled, Face Recognition Enabled
"""
import logging
import threading
import time
from typing import Any

import numpy as np

try:
    import cv2
    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False


class CameraPrivacyState:
    def __init__(self):
        self.camera_active: bool = True
        self.person_detection_enabled: bool = True
        self.face_recognition_enabled: bool = True


class CameraManager:
    """
    Manages local webcam capture with hardware-level release on pause/stop.
    """

    _instance = None
    _singleton_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, camera_index: int = 0):
        if getattr(self, "_initialized", False):
            return

        self._camera_index = camera_index
        self._cap = None
        self._lock = threading.RLock()
        self._latest_frame: np.ndarray | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self.privacy = CameraPrivacyState()
        self._initialized = True

    # ── Privacy & Lifecycle Controls ─────────────────────────────

    def start(self) -> bool:
        """Start the camera stream."""
        if not _HAS_CV2:
            return False

        with self._lock:
            if self._running:
                return True

            if not self.privacy.camera_active:
                return False

            self._cap = cv2.VideoCapture(self._camera_index)
            if not self._cap.isOpened():
                self._cap = None
                return False

            # Set fast low-latency resolution (640x480)
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

            self._running = True
            self._thread = threading.Thread(target=self._capture_loop, daemon=True, name="son-camera")
            self._thread.start()
            return True

    def stop(self):
        """Physically stop and release the camera device."""
        with self._lock:
            self._running = False
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None
            self._latest_frame = None

    def pause(self):
        """Pause camera capture (privacy kill-switch). Releases hardware."""
        with self._lock:
            self.privacy.camera_active = False
            self.stop()

    def resume(self) -> bool:
        """Resume camera capture."""
        with self._lock:
            self.privacy.camera_active = True
            return self.start()

    def set_person_detection_enabled(self, enabled: bool):
        self.privacy.person_detection_enabled = enabled

    def set_face_recognition_enabled(self, enabled: bool):
        self.privacy.face_recognition_enabled = enabled

    def is_available(self) -> bool:
        """Check if camera hardware is accessible."""
        if not _HAS_CV2:
            return False
        with self._lock:
            if self._running and self._cap is not None:
                return True
            # Probe device
            cap = cv2.VideoCapture(self._camera_index)
            opened = cap.isOpened()
            cap.release()
            return opened

    # ── Frame Access ─────────────────────────────────────────────

    def _capture_loop(self):
        """Continuous frame grabber running in background thread."""
        while self._running:
            if self._cap is None or not self.privacy.camera_active:
                time.sleep(0.1)
                continue

            ret, frame = self._cap.read()
            if ret and frame is not None:
                with self._lock:
                    self._latest_frame = frame
            time.sleep(0.03)  # ~30 FPS limit

    def get_frame(self) -> np.ndarray | None:
        """Get the latest captured frame (returns copy for thread safety)."""
        with self._lock:
            if not self.privacy.camera_active or self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    def get_privacy_status(self) -> dict[str, Any]:
        return {
            "camera_active": self.privacy.camera_active,
            "person_detection_enabled": self.privacy.person_detection_enabled,
            "face_recognition_enabled": self.privacy.face_recognition_enabled,
            "hardware_running": self._running and self._cap is not None,
        }
