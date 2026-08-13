# core/profiler.py — Performance Profiler & Request Tracing for SON V3
"""
Instruments every pipeline stage with precise timing.
Each request gets a unique ID for end-to-end traceability.

Usage:
    from core.profiler import RequestTracer, trace_stage

    tracer = RequestTracer()

    with tracer.trace("stt"):
        text = stt.transcribe(audio)

    with tracer.trace("llm"):
        response = brain.think(text)

    tracer.finish()  # logs full breakdown

    # Or as a decorator:
    @trace_stage("embedding")
    def embed(text):
        ...
"""
import time
import threading
import logging
import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any
from contextlib import contextmanager

from core.config import Config

# Dedicated performance logger
_perf_logger = None
_perf_lock = threading.Lock()


def _get_perf_logger() -> logging.Logger:
    """Get or create the dedicated performance logger."""
    global _perf_logger
    if _perf_logger is not None:
        return _perf_logger

    with _perf_lock:
        if _perf_logger is not None:
            return _perf_logger

        logger = logging.getLogger("son.performance")
        logger.setLevel(logging.INFO)
        logger.propagate = False  # Don't bubble up to root logger

        if not logger.handlers:
            log_file = Config.LOGS_DIR / "performance.log"
            handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)

        _perf_logger = logger
        return _perf_logger


# Global request counter (thread-safe)
_request_counter = 0
_counter_lock = threading.Lock()


def _next_request_id() -> str:
    """Generate a unique request ID: REQ-YYYYMMDD-NNN."""
    global _request_counter
    with _counter_lock:
        _request_counter += 1
        count = _request_counter
    date_str = datetime.now().strftime("%Y%m%d")
    return f"REQ-{date_str}-{count:04d}"


@dataclass
class StageResult:
    """Timing result for a single pipeline stage."""
    name: str
    duration_ms: float
    started_at: float
    ended_at: float
    metadata: dict = field(default_factory=dict)
    error: str | None = None


class RequestTracer:
    """
    Traces a single user request through the entire pipeline.

    Records timing for each stage (STT, memory, LLM, tools, TTS)
    and produces a structured performance log entry on finish.
    """

    def __init__(self, request_id: str | None = None):
        self.request_id = request_id or _next_request_id()
        self._start_time = time.perf_counter()
        self._wall_start = datetime.now().isoformat()
        self._stages: list[StageResult] = []
        self._active_stage: str | None = None
        self._active_start: float = 0.0
        self._metadata: dict[str, Any] = {}
        self._lock = threading.Lock()

    def set_metadata(self, key: str, value: Any):
        """Attach metadata to the request trace (e.g., intent type, model used)."""
        self._metadata[key] = value

    @contextmanager
    def trace(self, stage_name: str, **meta):
        """
        Context manager to time a pipeline stage.

        Usage:
            with tracer.trace("stt"):
                text = stt.transcribe(audio)
        """
        start = time.perf_counter()
        error = None
        try:
            yield self
        except Exception as e:
            error = str(e)
            raise
        finally:
            end = time.perf_counter()
            duration_ms = (end - start) * 1000
            result = StageResult(
                name=stage_name,
                duration_ms=round(duration_ms, 2),
                started_at=start,
                ended_at=end,
                metadata=meta,
                error=error,
            )
            with self._lock:
                self._stages.append(result)

    def record_stage(self, stage_name: str, duration_ms: float, **meta):
        """Manually record a stage timing (for cases where context manager doesn't fit)."""
        now = time.perf_counter()
        result = StageResult(
            name=stage_name,
            duration_ms=round(duration_ms, 2),
            started_at=now - (duration_ms / 1000),
            ended_at=now,
            metadata=meta,
        )
        with self._lock:
            self._stages.append(result)

    def get_stage_duration(self, stage_name: str) -> float | None:
        """Get duration of a specific stage in milliseconds."""
        with self._lock:
            for stage in self._stages:
                if stage.name == stage_name:
                    return stage.duration_ms
        return None

    def finish(self) -> dict:
        """
        Finalize the trace and log the full performance breakdown.

        Returns:
            Dict with all timing data for the request.
        """
        total_ms = (time.perf_counter() - self._start_time) * 1000

        with self._lock:
            stages_data = []
            for s in self._stages:
                entry = {
                    "stage": s.name,
                    "duration_ms": s.duration_ms,
                }
                if s.metadata:
                    entry["meta"] = s.metadata
                if s.error:
                    entry["error"] = s.error
                stages_data.append(entry)

        report = {
            "request_id": self.request_id,
            "timestamp": self._wall_start,
            "total_ms": round(total_ms, 2),
            "stages": stages_data,
            "metadata": self._metadata,
        }

        # Log to performance log
        try:
            perf_logger = _get_perf_logger()
            perf_logger.info(json.dumps(report, default=str))
        except Exception:
            pass  # Never let logging break the app

        return report

    def summary_string(self) -> str:
        """
        Human-readable summary for terminal/UI display.

        Example:
            REQ-20260814-0001 | Total: 2340ms
             ├── STT:     620ms
             ├── Memory:   74ms
             ├── LLM:    1800ms
             ├── Tool:    120ms
             └── TTS:     340ms
        """
        total_ms = (time.perf_counter() - self._start_time) * 1000

        with self._lock:
            lines = [f"{self.request_id} | Total: {total_ms:.0f}ms"]
            for i, s in enumerate(self._stages):
                connector = " └──" if i == len(self._stages) - 1 else " ├──"
                error_mark = " ✗" if s.error else ""
                lines.append(f"{connector} {s.name:<12s} {s.duration_ms:>8.1f}ms{error_mark}")

        return "\n".join(lines)


def trace_stage(stage_name: str, tracer_attr: str = "_tracer"):
    """
    Decorator to trace a method's execution time.

    The decorated method's object must have a RequestTracer
    stored in the attribute specified by `tracer_attr`.

    Usage:
        class Brain:
            def __init__(self):
                self._tracer = None

            @trace_stage("llm")
            def think(self, text):
                ...
    """
    def decorator(fn):
        def wrapper(self, *args, **kwargs):
            tracer = getattr(self, tracer_attr, None)
            if tracer and isinstance(tracer, RequestTracer):
                with tracer.trace(stage_name):
                    return fn(self, *args, **kwargs)
            return fn(self, *args, **kwargs)
        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        return wrapper
    return decorator


# ── Convenience: Global Profiling Stats ──────────────────────────

class ProfileStats:
    """
    Aggregates performance statistics across multiple requests.
    Used for the benchmark suite and health monitoring.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._stage_totals: dict[str, list[float]] = {}
        self._request_count = 0

    def record(self, report: dict):
        """Record a finished request's report."""
        with self._lock:
            self._request_count += 1
            for stage in report.get("stages", []):
                name = stage["stage"]
                ms = stage["duration_ms"]
                self._stage_totals.setdefault(name, []).append(ms)

    def summary(self) -> dict:
        """Get aggregate statistics."""
        with self._lock:
            result = {"request_count": self._request_count, "stages": {}}
            for name, times in self._stage_totals.items():
                if times:
                    result["stages"][name] = {
                        "count": len(times),
                        "avg_ms": round(sum(times) / len(times), 2),
                        "min_ms": round(min(times), 2),
                        "max_ms": round(max(times), 2),
                        "p50_ms": round(sorted(times)[len(times) // 2], 2),
                        "p95_ms": round(
                            sorted(times)[int(len(times) * 0.95)] if len(times) >= 20 else max(times), 2
                        ),
                    }
            return result


# Global stats instance
global_stats = ProfileStats()
