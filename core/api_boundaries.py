# core/api_boundaries.py — SON V4 Hybrid Architecture API Stubs
import logging
from core.config import Config

logger = Config.get_logger(__name__)

class RustRuntimeClient:
    """
    Interface for the Rust Background Engine.
    In the future, Python will hand off VAD, Audio Capture, and background IPC loops to Rust here.
    """
    def __init__(self):
        self.connected = False

    def start_audio_capture(self):
        logger.info("Delegating Audio Capture to Rust Runtime... (STUB)")

    def dispatch_event(self, event_type: str, payload: dict):
        logger.info(f"Sending event to Rust Event Bus: {event_type} (STUB)")


class WindowsIntegrationClient:
    """
    Interface for the C# Windows Specialist.
    In the future, Python will hand off UI Automation and Notifications to C# here.
    """
    def __init__(self):
        self.connected = False

    def send_notification(self, title: str, message: str):
        logger.info(f"Delegating Windows Notification to C# Specialist: {title} (STUB)")

    def interact_with_ui(self, element_id: str, action: str):
        logger.info(f"Delegating UI Interaction to C# Specialist: {element_id} -> {action} (STUB)")


class NativeVisionClient:
    """
    Interface for the C++ GPU Vision Pipeline.
    In the future, Python will consume pre-processed bounding boxes and identities from C++.
    """
    def __init__(self):
        self.connected = False

    def request_person_detection(self):
        logger.info("Requesting person detection from C++ Vision Pipeline... (STUB)")
        return {"person_present": False, "count": 0}
