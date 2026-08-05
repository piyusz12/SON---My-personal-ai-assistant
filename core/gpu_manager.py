# core/gpu_manager.py — GPU VRAM Management for SON V3
"""
Manages RTX 4060 Laptop GPU (8 GB VRAM) allocation across models.

Uses pynvml (NVIDIA Management Library) for direct GPU queries
instead of spawning nvidia-smi subprocess — ~100x faster.

VRAM Budget:
    Ollama LLM (qwen3:8b)      ~5.0 GB
    Faster-Whisper (large-v3)   ~1.5 GB
    Embedding model             ~0.5 GB
    TTS (Piper ONNX)            ~0.3 GB
    GUI (OpenGL)                ~0.1 GB
    ──────────────────────────────────
    Total                       ~7.4 GB / 8.0 GB

Usage:
    from core.gpu_manager import GPUManager
    
    gpu = GPUManager()
    gpu.log_vram_status()
    
    with gpu.reserve_vram("whisper", 1500):
        # Whisper model loaded here
        pass
"""
import threading
import logging
import contextlib
from typing import Generator

from core.config import Config

logger = Config.get_logger(__name__)

# Try to import pynvml for direct GPU access
_PYNVML_AVAILABLE = False
try:
    import pynvml
    _PYNVML_AVAILABLE = True
except ImportError:
    logger.warning(
        "pynvml not installed. GPU metrics will use nvidia-smi fallback. "
        "Install with: pip install pynvml"
    )


class GPUManager:
    """
    VRAM-aware GPU resource manager for the RTX 4060 Laptop GPU.
    
    Provides:
    - Fast GPU metrics via pynvml (no subprocess)
    - VRAM reservation tracking
    - Model lifecycle management
    - OOM prevention
    """
    
    # VRAM budget (MB) for each model
    VRAM_BUDGET = {
        "llm":       5000,   # qwen3:8b
        "whisper":   1500,   # faster-whisper large-v3
        "embedding": 500,    # nomic-embed-text
        "tts":       300,    # Piper ONNX-GPU
        "gui":       100,    # OpenGL orb rendering
    }
    TOTAL_VRAM_MB = 8188     # RTX 4060 Laptop
    SAFETY_MARGIN_MB = 512   # Keep ~500 MB free for CUDA overhead
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton — one GPU manager per process."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._handle = None
        self._reservations: dict[str, int] = {}  # name -> MB
        self._res_lock = threading.Lock()
        
        if _PYNVML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                name = pynvml.nvmlDeviceGetName(self._handle)
                logger.info(f"GPUManager: {name} initialized via pynvml")
            except Exception as e:
                logger.error(f"Failed to initialize pynvml: {e}")
                self._handle = None
        
        self._initialized = True
    
    # ── Fast GPU Metrics (pynvml) ────────────────────────────────
    
    def get_metrics(self) -> dict:
        """
        Get current GPU metrics without spawning a subprocess.
        
        Returns:
            Dict with: gpu_util, vram_used_mb, vram_total_mb, 
                       gpu_temp_c, gpu_name, power_draw_w
        """
        if not _PYNVML_AVAILABLE or self._handle is None:
            return self._get_metrics_fallback()
        
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(self._handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
            temp = pynvml.nvmlDeviceGetTemperature(
                self._handle, pynvml.NVML_TEMPERATURE_GPU
            )
            
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(self._handle) / 1000.0  # mW → W
            except pynvml.NVMLError:
                power = 0.0
            
            name = pynvml.nvmlDeviceGetName(self._handle)
            
            return {
                "gpu_name": name,
                "gpu_util": float(util.gpu),
                "vram_used_mb": round(mem.used / (1024 ** 2), 1),
                "vram_total_mb": round(mem.total / (1024 ** 2), 1),
                "vram_free_mb": round(mem.free / (1024 ** 2), 1),
                "gpu_temp_c": float(temp),
                "power_draw_w": round(power, 1),
            }
        except Exception as e:
            logger.error(f"pynvml metrics error: {e}")
            return self._get_metrics_fallback()
    
    def _get_metrics_fallback(self) -> dict:
        """Fallback: use nvidia-smi subprocess."""
        import subprocess
        try:
            res = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,name,power.draw",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3
            )
            if res.returncode == 0:
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                if len(parts) >= 5:
                    vram_used = float(parts[1])
                    vram_total = float(parts[2])
                    return {
                        "gpu_name": parts[4] if len(parts) > 4 else "NVIDIA GPU",
                        "gpu_util": float(parts[0]),
                        "vram_used_mb": vram_used,
                        "vram_total_mb": vram_total,
                        "vram_free_mb": vram_total - vram_used,
                        "gpu_temp_c": float(parts[3]),
                        "power_draw_w": float(parts[5]) if len(parts) > 5 else 0.0,
                    }
        except Exception as e:
            logger.error(f"nvidia-smi fallback failed: {e}")
        
        return {
            "gpu_name": "Unknown",
            "gpu_util": 0.0,
            "vram_used_mb": 0.0,
            "vram_total_mb": self.TOTAL_VRAM_MB,
            "vram_free_mb": self.TOTAL_VRAM_MB,
            "gpu_temp_c": 0.0,
            "power_draw_w": 0.0,
        }
    
    # ── VRAM Reservation System ──────────────────────────────────
    
    def can_allocate(self, mb: int) -> bool:
        """Check if we can allocate the requested VRAM without OOM."""
        metrics = self.get_metrics()
        return metrics["vram_free_mb"] >= (mb + self.SAFETY_MARGIN_MB)
    
    @contextlib.contextmanager
    def reserve_vram(self, name: str, mb: int) -> Generator:
        """
        Context manager to track VRAM reservation.
        
        Doesn't actually allocate GPU memory — that's done by the model
        frameworks. This provides tracking and OOM prevention.
        
        Args:
            name: Reservation name (e.g., "whisper", "llm").
            mb: Expected VRAM usage in MB.
        
        Yields:
            True if reservation was accepted.
        
        Raises:
            MemoryError: If allocation would exceed safe VRAM limits.
        """
        with self._res_lock:
            total_reserved = sum(self._reservations.values())
            max_usable = self.TOTAL_VRAM_MB - self.SAFETY_MARGIN_MB
            
            if total_reserved + mb > max_usable:
                raise MemoryError(
                    f"GPU VRAM reservation for '{name}' ({mb} MB) would exceed "
                    f"safe limits. Reserved: {total_reserved} MB, "
                    f"Max usable: {max_usable} MB"
                )
            
            self._reservations[name] = mb
            logger.info(
                f"GPU VRAM reserved: {name} = {mb} MB "
                f"(total reserved: {total_reserved + mb} MB)"
            )
        
        try:
            yield True
        finally:
            with self._res_lock:
                self._reservations.pop(name, None)
                logger.info(f"GPU VRAM released: {name}")
    
    def get_reservation_summary(self) -> dict:
        """Get current VRAM reservation breakdown."""
        with self._res_lock:
            total = sum(self._reservations.values())
            return {
                "reservations": dict(self._reservations),
                "total_reserved_mb": total,
                "total_vram_mb": self.TOTAL_VRAM_MB,
                "available_mb": self.TOTAL_VRAM_MB - total - self.SAFETY_MARGIN_MB,
            }
    
    # ── Convenience ──────────────────────────────────────────────
    
    def log_vram_status(self):
        """Log current VRAM status."""
        metrics = self.get_metrics()
        res = self.get_reservation_summary()
        logger.info(
            f"GPU: {metrics['gpu_name']} | "
            f"VRAM: {metrics['vram_used_mb']:.0f}/{metrics['vram_total_mb']:.0f} MB | "
            f"Util: {metrics['gpu_util']:.0f}% | "
            f"Temp: {metrics['gpu_temp_c']:.0f}°C | "
            f"Reservations: {res['reservations']}"
        )
    
    def shutdown(self):
        """Clean up pynvml."""
        if _PYNVML_AVAILABLE:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
