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
import contextlib

class CameraPrivacyState:
    def __init__(self, camera_active: bool = False):
        self.camera_active: bool = camera_active
        self.person_detection_enabled: bool = True
        self.face_recognition_enabled: bool = True


class CameraManager:
    """
    Manages local webcam capture with lazy opening and auto-standby hardware release.
    When not in use for >3 seconds, the camera is physically closed/released so the
    webcam LED turns off, saving battery and ensuring absolute hardware privacy.
    """

    _instance = None
    _singleton_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, camera_index: int = 0, auto_standby_seconds: float = 3.0):
        if getattr(self, "_initialized", False):
            return

        self._camera_index = camera_index
        self._auto_standby_seconds = auto_standby_seconds
        self._cap = None
        self._lock = threading.RLock()
        self._latest_frame: np.ndarray | None = None
        self._running = False
        self._last_access_time = 0.0
        self._thread: threading.Thread | None = None

        auto_start = False
        try:
            import config
            auto_start = getattr(config, "CAMERA_AUTO_START", False)
        except Exception:
            pass
        self.privacy = CameraPrivacyState(camera_active=auto_start)
        self._initialized = True

    # ── Privacy & Lifecycle Controls ─────────────────────────────

    def _open_hardware(self) -> bool:
        """Internal helper to initialize and open the camera device."""
        if not _HAS_CV2 or not self.privacy.camera_active:
            return False

        if self._cap is not None and self._cap.isOpened():
            return True

        try:
            self._cap = cv2.VideoCapture(self._camera_index)
            if not self._cap.isOpened():
                self._cap = None
                return False

            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._running = True
            self._last_access_time = time.time()

            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(
                    target=self._capture_loop, daemon=True, name="son-camera"
                )
                self._thread.start()
            return True
        except Exception:
            self._cap = None
            return False

    def start(self) -> bool:
        """Start the camera stream (auto-wakes on demand)."""
        with self._lock:
            if not self.privacy.camera_active:
                return False
            return self._open_hardware()

    def stop(self):
        """Physically stop and release the camera device (turns off webcam LED)."""
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
        """Pause camera capture (privacy kill-switch). Releases hardware immediately."""
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
            if self._running and self._cap is not None and self._cap.isOpened():
                return True
            try:
                cap = cv2.VideoCapture(self._camera_index)
                opened = cap.isOpened()
                cap.release()
                return opened
            except Exception:
                return False

    # ── Frame Access & Auto-Standby Loop ─────────────────────────

    def _capture_loop(self):
        """
        Background frame grabber with automatic standby idle shutdown.
        If no frame is accessed for > auto_standby_seconds, releases hardware.
        """
        while self._running:
            # Check inactivity timeout
            if time.time() - self._last_access_time > self._auto_standby_seconds:
                # Inactive — release hardware to turn off webcam light
                self.stop()
                break

            if self._cap is None or not self.privacy.camera_active:
                time.sleep(0.05)
                continue

            ret, frame = self._cap.read()
            if ret and frame is not None:
                with self._lock:
                    self._latest_frame = frame
            time.sleep(0.03)  # ~30 FPS

    def get_frame(self, auto_wake: bool = True) -> np.ndarray | None:
        """
        Get the latest captured frame.
        If camera is asleep and auto_wake is True, lazily wakes and captures frame.
        """
        with self._lock:
            if not self.privacy.camera_active:
                return None

            self._last_access_time = time.time()

            if self._cap is None or not self._cap.isOpened():
                if auto_wake:
                    if not self._open_hardware():
                        return None
                    # Grab initial frame
                    ret, frame = self._cap.read()
                    if ret and frame is not None:
                        self._latest_frame = frame
                        return frame.copy()
                return None

            if self._latest_frame is None:
                ret, frame = self._cap.read()
                if ret and frame is not None:
                    self._latest_frame = frame
                    return frame.copy()
                return None

            return self._latest_frame.copy()

    def capture_single_frame(self) -> np.ndarray | None:
        """Capture a single frame on demand and immediately release hardware."""
        with self._lock:
            if not self.privacy.camera_active or not _HAS_CV2:
                return None
            try:
                cap = cv2.VideoCapture(self._camera_index)
                if not cap.isOpened():
                    return None
                # Discard 2 warm-up frames for auto-exposure/white-balance
                for _ in range(2):
                    cap.read()
                ret, frame = cap.read()
                cap.release()
                return frame if (ret and frame is not None) else None
            except Exception:
                return None

    @contextlib.contextmanager
    def session(self):
        """Context manager: opens camera and guarantees immediate release on exit."""
        frame = self.get_frame(auto_wake=True)
        try:
            yield frame
        finally:
            self.stop()

    def get_privacy_status(self) -> dict[str, Any]:
        return {
            "camera_active": self.privacy.camera_active,
            "person_detection_enabled": self.privacy.person_detection_enabled,
            "face_recognition_enabled": self.privacy.face_recognition_enabled,
            "hardware_running": self._running and self._cap is not None and self._cap.isOpened(),
            "hardware_status": "CAPTURING" if (self._cap is not None and self._cap.isOpened()) else "STANDBY",
        }
