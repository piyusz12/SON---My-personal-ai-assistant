# core/event_bus.py — Asynchronous Structured Event Bus for SON V3
"""
Thread-safe, decoupled event publisher and subscriber system for SON V3.
Enables real-time telemetry streaming to:
  - C# WPF Desktop HUD (Named Pipe)
  - Godot Visual Holographic Engine (WebSocket)
  - Remote / Web Console (FastAPI WebSocket)
  - Audio & Voice state transitions
  - Security audit and health tracking
"""

import time
import logging
import threading
from enum import Enum
from typing import Any, Callable, Optional
from dataclasses import dataclass, field

from core.config import Config

logger = Config.get_logger(__name__)


class EventType(str, Enum):
    SON_STARTED = "son_started"
    SON_READY = "son_ready"
    SON_SHUTDOWN = "son_shutdown"
    LISTENING = "listening"
    TRANSCRIPTION = "transcription"
    THINKING = "thinking"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    SPEAKING = "speaking"
    VISION_ACTIVE = "vision_active"
    WARNING = "warning"
    ERROR = "error"
    SYSTEM_STATUS = "system_status"
    REQUEST_RECEIVED = "request_received"
    REQUEST_COMPLETED = "request_completed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RESOLVED = "approval_resolved"


@dataclass
class SonEvent:
    """Structured event envelope published across the system."""
    event_type: EventType
    timestamp: float = field(default_factory=time.time)
    source: str = "core"
    payload: dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    request_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value if isinstance(self.event_type, EventType) else str(self.event_type),
            "timestamp": self.timestamp,
            "source": self.source,
            "payload": self.payload,
            "session_id": self.session_id,
            "request_id": self.request_id,
        }


class EventBus:
    """
    Central event broker supporting synchronous and asynchronous subscribers.
    Thread-safe with subscription filtering by EventType.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._subscribers: dict[str, list[Callable[[SonEvent], None]]] = {}
        self._global_subscribers: list[Callable[[SonEvent], None]] = []
        self._sub_lock = threading.RLock()
        self._history: list[SonEvent] = []
        self._history_max = 500
        self._initialized = True
        logger.info("EventBus initialized")

    def subscribe(self, event_type: EventType | str, handler: Callable[[SonEvent], None]):
        """Subscribe a callback to a specific EventType."""
        key = event_type.value if isinstance(event_type, EventType) else str(event_type)
        with self._sub_lock:
            if key not in self._subscribers:
                self._subscribers[key] = []
            if handler not in self._subscribers[key]:
                self._subscribers[key].append(handler)

    def subscribe_all(self, handler: Callable[[SonEvent], None]):
        """Subscribe a callback to all events (e.g. for WebSocket forwarding)."""
        with self._sub_lock:
            if handler not in self._global_subscribers:
                self._global_subscribers.append(handler)

    def unsubscribe(self, event_type: EventType | str, handler: Callable[[SonEvent], None]):
        """Remove a subscription."""
        key = event_type.value if isinstance(event_type, EventType) else str(event_type)
        with self._sub_lock:
            if key in self._subscribers and handler in self._subscribers[key]:
                self._subscribers[key].remove(handler)
            if handler in self._global_subscribers:
                self._global_subscribers.remove(handler)

    def publish(
        self,
        event_type: EventType | str,
        payload: Optional[dict[str, Any]] = None,
        source: str = "core",
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> SonEvent:
        """Publish an event to all interested subscribers."""
        ev_type = event_type if isinstance(event_type, EventType) else EventType(str(event_type))
        event = SonEvent(
            event_type=ev_type,
            timestamp=time.time(),
            source=source,
            payload=payload or {},
            session_id=session_id,
            request_id=request_id,
        )

        with self._sub_lock:
            self._history.append(event)
            if len(self._history) > self._history_max:
                self._history.pop(0)

            handlers = list(self._global_subscribers)
            key = ev_type.value
            if key in self._subscribers:
                handlers.extend(self._subscribers[key])

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in EventBus handler for event '{key}': {e}", exc_info=True)

        return event

    def get_recent_events(self, limit: int = 50) -> list[SonEvent]:
        """Return the most recent events."""
        with self._sub_lock:
            return list(self._history[-limit:])

    def clear(self):
        """Reset subscribers and history (useful for testing)."""
        with self._sub_lock:
            self._subscribers.clear()
            self._global_subscribers.clear()
            self._history.clear()


# Global EventBus instance
event_bus = EventBus()
