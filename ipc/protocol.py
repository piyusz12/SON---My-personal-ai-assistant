# ipc/protocol.py — JSON Event Protocol for Python <-> Godot Frontend
"""
Defines strongly-typed messages exchanged over WebSocket between
the SON Python AI backend and the Godot 3D/HUD frontend.
"""
import json
import time
from enum import Enum
from dataclasses import dataclass, asdict, field
from typing import Any


class EventType(str, Enum):
    # Backend -> Frontend (Outbound)
    STATE_CHANGE = "state_change"
    AUDIO_WAVEFORM = "audio_waveform"
    THOUGHT_PIPELINE = "thought_pipeline"
    SYSTEM_TELEMETRY = "system_telemetry"
    PERCEPTION_UPDATE = "perception_update"
    SUBTITLE = "subtitle"
    SOUND_CUE = "sound_cue"
    COMMAND_RESULT = "command_result"

    # Frontend -> Backend (Inbound)
    USER_PROMPT = "user_prompt"
    VOICE_TRIGGER = "voice_trigger"
    TOGGLE_CAMERA = "toggle_camera"
    TOGGLE_MIC = "toggle_mic"
    HUD_ACTION = "hud_action"


class VisualState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    EXECUTING = "executing"
    SEARCHING = "searching"
    VISION = "vision"
    WARNING = "warning"
    ERROR = "error"
    SLEEP = "sleep"


@dataclass
class IPCMessage:
    event: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps({
            "event": self.event,
            "data": self.data,
            "timestamp": self.timestamp,
        })

    @classmethod
    def from_json(cls, text: str) -> "IPCMessage":
        payload = json.loads(text)
        return cls(
            event=payload.get("event", "unknown"),
            data=payload.get("data", {}),
            timestamp=payload.get("timestamp", time.time()),
        )
