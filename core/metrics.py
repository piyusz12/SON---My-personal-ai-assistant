import time
from collections import defaultdict
import threading

class PerformanceMetrics:
    """Thread-safe performance monitoring and profiling."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._timings = defaultdict(list)
            cls._instance._lock = threading.Lock()
        return cls._instance
    
    def record(self, operation: str, duration_ms: float):
        """Record the duration of an operation."""
        with self._lock:
            self._timings[operation].append(duration_ms)
            # Keep last 1000 measurements
            if len(self._timings[operation]) > 1000:
                self._timings[operation] = self._timings[operation][-1000:]
    
    def get_stats(self, operation: str) -> dict:
        """Get statistics for a specific operation."""
        timings = self._timings.get(operation, [])
        if not timings:
            return {}
        
        sorted_timings = sorted(timings)
        return {
            "count": len(timings),
            "avg_ms": sum(timings) / len(timings),
            "p50_ms": sorted_timings[len(timings)//2],
            "p95_ms": sorted_timings[int(len(timings)*0.95)],
            "p99_ms": sorted_timings[int(len(timings)*0.99)],
        }
    
    def clear(self):
        """Clear all recorded metrics."""
        with self._lock:
            self._timings.clear()
