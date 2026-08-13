# hud/state.py — State Machine & Visual Aesthetics for SON Holographic HUD
"""
Defines the visual state machine for SON V3:
States: IDLE, LISTENING, THINKING, SPEAKING, EXECUTING, SEARCHING, VISION, WARNING, ERROR, SLEEP

Each state drives:
- Particle speed, count, and radius
- Gyroscopic ring rotation velocity & tilt
- Core pulse frequency, glow intensity, and color palette
- Waveform amplitude responsiveness
"""
import math
from dataclasses import dataclass
from enum import Enum
from PySide6.QtGui import QColor


class HUDState(Enum):
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
class StateVisualConfig:
    primary_color: QColor
    secondary_color: QColor
    accent_color: QColor
    glow_color: QColor
    ring_speed: float       # degrees per frame
    pulse_speed: float      # radians per frame
    particle_speed: float   # velocity multiplier
    particle_count: int     # active particles
    wave_amplitude: float   # audio waveform reaction factor
    glow_radius: int        # blur radius for core
    status_label: str       # human-readable state label


STATE_CONFIGS: dict[HUDState, StateVisualConfig] = {
    HUDState.IDLE: StateVisualConfig(
        primary_color=QColor(0, 240, 255, 220),       # Electric Cyan
        secondary_color=QColor(0, 150, 255, 140),     # Deep Sky Blue
        accent_color=QColor(255, 255, 255, 240),      # Pure White
        glow_color=QColor(0, 240, 255, 45),
        ring_speed=0.6,
        pulse_speed=0.03,
        particle_speed=0.5,
        particle_count=35,
        wave_amplitude=0.2,
        glow_radius=25,
        status_label="SYSTEM READY",
    ),
    HUDState.LISTENING: StateVisualConfig(
        primary_color=QColor(0, 255, 170, 240),       # Neon Aquamarine
        secondary_color=QColor(0, 200, 255, 160),     # Cyan
        accent_color=QColor(255, 255, 255, 255),
        glow_color=QColor(0, 255, 170, 70),
        ring_speed=1.5,
        pulse_speed=0.08,
        particle_speed=1.2,
        particle_count=50,
        wave_amplitude=1.5,
        glow_radius=35,
        status_label="LISTENING...",
    ),
    HUDState.THINKING: StateVisualConfig(
        primary_color=QColor(180, 70, 255, 240),      # Holographic Purple / Violet
        secondary_color=QColor(0, 240, 255, 180),     # Cyan accent
        accent_color=QColor(255, 220, 255, 255),
        glow_color=QColor(180, 70, 255, 65),
        ring_speed=2.8,
        pulse_speed=0.12,
        particle_speed=2.0,
        particle_count=60,
        wave_amplitude=0.4,
        glow_radius=30,
        status_label="PROCESSING...",
    ),
    HUDState.SPEAKING: StateVisualConfig(
        primary_color=QColor(0, 230, 255, 250),       # High-Energy Cyan
        secondary_color=QColor(255, 180, 0, 180),     # Gold Highlights
        accent_color=QColor(255, 255, 255, 255),
        glow_color=QColor(0, 230, 255, 80),
        ring_speed=1.2,
        pulse_speed=0.10,
        particle_speed=1.4,
        particle_count=45,
        wave_amplitude=2.0,
        glow_radius=40,
        status_label="TRANSMITTING",
    ),
    HUDState.EXECUTING: StateVisualConfig(
        primary_color=QColor(255, 170, 0, 240),       # Amber Gold (JARVIS Tactical)
        secondary_color=QColor(255, 100, 0, 160),     # Deep Orange
        accent_color=QColor(255, 255, 200, 255),
        glow_color=QColor(255, 170, 0, 60),
        ring_speed=2.2,
        pulse_speed=0.07,
        particle_speed=1.6,
        particle_count=50,
        wave_amplitude=0.5,
        glow_radius=32,
        status_label="EXECUTING COMMAND",
    ),
    HUDState.SEARCHING: StateVisualConfig(
        primary_color=QColor(0, 190, 255, 240),       # Sci-Fi Blue
        secondary_color=QColor(100, 255, 218, 170),   # Teal
        accent_color=QColor(255, 255, 255, 255),
        glow_color=QColor(0, 190, 255, 60),
        ring_speed=3.0,
        pulse_speed=0.09,
        particle_speed=2.2,
        particle_count=55,
        wave_amplitude=0.6,
        glow_radius=28,
        status_label="SEARCHING DATA",
    ),
    HUDState.VISION: StateVisualConfig(
        primary_color=QColor(0, 255, 200, 240),       # Cyber Emerald
        secondary_color=QColor(0, 160, 255, 160),     # Blue
        accent_color=QColor(255, 255, 255, 255),
        glow_color=QColor(0, 255, 200, 65),
        ring_speed=1.8,
        pulse_speed=0.06,
        particle_speed=1.0,
        particle_count=40,
        wave_amplitude=0.3,
        glow_radius=30,
        status_label="OPTICAL SENSOR ACTIVE",
    ),
    HUDState.WARNING: StateVisualConfig(
        primary_color=QColor(255, 180, 0, 250),       # Hazard Amber
        secondary_color=QColor(255, 80, 0, 180),      # Fire Orange
        accent_color=QColor(255, 255, 255, 255),
        glow_color=QColor(255, 180, 0, 75),
        ring_speed=2.0,
        pulse_speed=0.14,
        particle_speed=1.8,
        particle_count=45,
        wave_amplitude=0.8,
        glow_radius=35,
        status_label="SYSTEM ADVISORY",
    ),
    HUDState.ERROR: StateVisualConfig(
        primary_color=QColor(255, 40, 70, 250),       # Neon Crimson
        secondary_color=QColor(180, 0, 40, 180),      # Deep Ruby
        accent_color=QColor(255, 200, 200, 255),
        glow_color=QColor(255, 40, 70, 85),
        ring_speed=3.5,
        pulse_speed=0.18,
        particle_speed=2.5,
        particle_count=60,
        wave_amplitude=1.0,
        glow_radius=40,
        status_label="SYSTEM ALERT",
    ),
    HUDState.SLEEP: StateVisualConfig(
        primary_color=QColor(0, 120, 160, 120),       # Dim Cyan
        secondary_color=QColor(0, 60, 100, 80),       # Dark Slate
        accent_color=QColor(180, 220, 240, 160),
        glow_color=QColor(0, 120, 160, 20),
        ring_speed=0.2,
        pulse_speed=0.015,
        particle_speed=0.2,
        particle_count=15,
        wave_amplitude=0.05,
        glow_radius=15,
        status_label="STANDBY MODE",
    ),
}
