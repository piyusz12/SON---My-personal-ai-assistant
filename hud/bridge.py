# hud/bridge.py — Thread-Safe Event Bridge Between Orchestrator & PySide6 HUD
"""
Provides Qt Signals and thread-safe dispatchers to communicate between
the background SON orchestrator threads and the PySide6 UI thread.
"""
from PySide6.QtCore import QObject, Signal
from hud.state import HUDState


class HUDEventBridge(QObject):
    """
    Qt Signal Bridge for thread-safe cross-thread UI updates.
    """
    # State change signal: (HUDState, activity_text)
    sig_state_changed = Signal(object, str)

    # Audio level signal: (float 0.0 to 1.0)
    sig_audio_level = Signal(float)

    # Pipeline stage signal: (stage_idx int, description str)
    sig_pipeline_stage = Signal(int, str)

    # Subtitle signal: (speaker str, text str)
    sig_subtitle = Signal(str, str)

    # Perception signal: (camera_active bool, person_count int, name str, confidence float)
    sig_perception_update = Signal(bool, int, str, float)

    # System metrics signal: (cpu float, gpu float, vram_gb float, ram_gb float)
    sig_metrics_update = Signal(float, float, float, float)

    # Mode toggle: (fullscreen bool)
    sig_toggle_fullscreen = Signal(bool)

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def notify_state(self, state: HUDState, activity_text: str = ""):
        self.sig_state_changed.emit(state, activity_text)

    def notify_audio(self, level: float):
        self.sig_audio_level.emit(level)

    def notify_pipeline(self, stage_idx: int, description: str):
        self.sig_pipeline_stage.emit(stage_idx, description)

    def notify_subtitle(self, speaker: str, text: str):
        self.sig_subtitle.emit(speaker, text)

    def notify_perception(self, active: bool, person_count: int, name: str | None = None, confidence: float = 0.0):
        self.sig_perception_update.emit(active, person_count, name or "None", confidence)

    def notify_metrics(self, cpu: float, gpu: float, vram_gb: float, ram_gb: float):
        self.sig_metrics_update.emit(cpu, gpu, vram_gb, ram_gb)
