# core/thinking.py — Real-Time Thinking Visibility for SON V3
"""
Shows Dad exactly what SON is thinking and doing at every pipeline stage,
with precise per-step timing — in real time as it happens.

Architecture:
    ThinkingTracker is created per-request in _respond() and passed
    through the pipeline. Each stage uses tracker.step() to narrate
    what's happening, with automatic timing and UI updates.

Usage:
    tracker = ThinkingTracker(ui=self.ui, hud_bridge=self.hud_bridge)
    tracker.begin("open chrome for me")

    with tracker.step("Classifying intent", icon="🔍"):
        intent = router.classify(text)
    tracker.detail("Intent: COMMAND → app_open (confidence: 0.99)")

    with tracker.step("Executing command", icon="⚡"):
        result = commands.handle(text)

    tracker.finish()  # prints full summary with total time
"""
import time
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from core.config import Config

logger = Config.get_logger(__name__)

# Step icons for each pipeline stage
STAGE_ICONS = {
    "intent":       "🔍",
    "memory":       "🧠",
    "codebase":     "📂",
    "llm":          "🤖",
    "tool":         "🔧",
    "command":      "⚡",
    "tts":          "🔊",
    "stt":          "🎤",
    "vision":       "👁️",
    "camera":       "📷",
    "search":       "🌐",
    "embedding":    "📐",
    "cache":        "💾",
    "default":      "⚙️",
}


@dataclass
class ThinkingStep:
    """A single step in SON's thinking process."""
    name: str
    icon: str
    started_at: float
    ended_at: float | None = None
    duration_ms: float | None = None
    detail: str | None = None
    status: str = "running"  # running, done, error
    children: list["ThinkingStep"] = field(default_factory=list)


class ThinkingTracker:
    """
    Real-time thinking narrator for SON.

    Tracks every pipeline step with timing, emits live updates
    to the terminal UI and HUD bridge as each step starts/completes.
    """

    def __init__(self, ui=None, hud_bridge=None):
        self._ui = ui
        self._hud_bridge = hud_bridge
        self._steps: list[ThinkingStep] = []
        self._current_step: ThinkingStep | None = None
        self._start_time: float = 0.0
        self._user_input: str = ""
        self._lock = threading.Lock()
        self._step_index = 0

    def begin(self, user_input: str):
        """Start tracking a new request. Call at the top of _respond()."""
        self._start_time = time.perf_counter()
        self._user_input = user_input
        self._steps.clear()
        self._step_index = 0

        if self._ui:
            self._ui.show_thinking_start(user_input)

    @contextmanager
    def step(self, name: str, icon: str | None = None):
        """
        Context manager to track and display a single thinking step.

        Usage:
            with tracker.step("Classifying intent", icon="🔍"):
                result = router.classify(text)
        """
        if icon is None:
            # Auto-detect icon from name
            name_lower = name.lower()
            icon = STAGE_ICONS.get("default")
            for key, ico in STAGE_ICONS.items():
                if key in name_lower:
                    icon = ico
                    break

        step_obj = ThinkingStep(
            name=name,
            icon=icon,
            started_at=time.perf_counter(),
        )

        with self._lock:
            self._steps.append(step_obj)
            self._current_step = step_obj
            self._step_index += 1
            step_idx = self._step_index

        # Emit step-start to UI
        if self._ui:
            self._ui.show_thinking_step(step_idx, icon, name, status="running")

        # Emit to HUD bridge
        if self._hud_bridge:
            if hasattr(self._hud_bridge, "notify_thinking_step"):
                self._hud_bridge.notify_thinking_step(step_idx, icon, name, status="running")
            elif hasattr(self._hud_bridge, "notify_pipeline"):
                self._hud_bridge.notify_pipeline(step_idx, f"{icon} {name}")

        error_occurred = None
        try:
            yield step_obj
        except Exception as e:
            error_occurred = e
            step_obj.status = "error"
            raise
        finally:
            step_obj.ended_at = time.perf_counter()
            step_obj.duration_ms = (step_obj.ended_at - step_obj.started_at) * 1000

            if error_occurred is None:
                step_obj.status = "done"

            with self._lock:
                self._current_step = None

            # Emit step-complete to UI with timing
            if self._ui:
                self._ui.show_thinking_step(
                    step_idx, icon, name,
                    status=step_obj.status,
                    duration_ms=step_obj.duration_ms,
                    detail=step_obj.detail,
                )

            # Emit step-complete to HUD bridge
            if self._hud_bridge and hasattr(self._hud_bridge, "notify_thinking_step"):
                self._hud_bridge.notify_thinking_step(
                    step_idx, icon, name,
                    status=step_obj.status,
                    duration_ms=step_obj.duration_ms or 0.0,
                )

    def detail(self, text: str):
        """
        Add a detail line to the most recently completed or current step.
        Displays as an indented sub-line in the thinking panel.

        Usage:
            with tracker.step("Querying memories"):
                memories = memory.recall(text)
            tracker.detail(f"Found {len(memories)} relevant memories")
        """
        with self._lock:
            # Attach to the last step
            if self._steps:
                target = self._steps[-1]
                target.detail = text

        if self._ui:
            self._ui.show_thinking_detail(text)

    def finish(self) -> dict:
        """
        Finalize the thinking trace. Prints the total time summary.

        Returns:
            Dict with step breakdown for logging.
        """
        total_ms = (time.perf_counter() - self._start_time) * 1000

        # Build summary data
        with self._lock:
            steps_data = []
            for s in self._steps:
                entry = {
                    "name": s.name,
                    "duration_ms": round(s.duration_ms, 2) if s.duration_ms else 0,
                    "status": s.status,
                }
                if s.detail:
                    entry["detail"] = s.detail
                steps_data.append(entry)

        summary = {
            "total_ms": round(total_ms, 2),
            "steps": steps_data,
            "step_count": len(steps_data),
        }

        # Show the final timing summary in UI
        if self._ui:
            self._ui.show_thinking_summary(total_ms, steps_data)

        # Emit to HUD bridge
        if self._hud_bridge and hasattr(self._hud_bridge, "notify_thinking_summary"):
            self._hud_bridge.notify_thinking_summary(total_ms, len(steps_data))

        # Log to performance logger
        logger.debug(f"ThinkingTrace: {total_ms:.0f}ms total, {len(steps_data)} steps")

        return summary

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time since begin() in milliseconds."""
        return (time.perf_counter() - self._start_time) * 1000

    @property
    def steps(self) -> list[ThinkingStep]:
        """Get all recorded steps."""
        with self._lock:
            return list(self._steps)
