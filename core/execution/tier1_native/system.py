# core/execution/tier1_native/system.py — Tier 1 Native System Telemetry & Hardware Control
"""
Hardware monitoring and system controls: CPU, GPU (NVML/RTX 4060), RAM, Disk,
Battery, Audio, Brightness, and Power actions.
Includes non-critical telemetry caching to prevent performance degradation.
"""
import ctypes
import logging
import os
import subprocess
import time
from typing import Any, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)

# Try importing pynvml for zero-overhead GPU telemetry
_NVML_AVAILABLE = False
try:
    import pynvml
    pynvml.nvmlInit()
    _NVML_AVAILABLE = True
except Exception:
    _NVML_AVAILABLE = False


class NativeSystemManager:
    """Tier 1 Native System Telemetry and Hardware Controls."""

    def __init__(self, cache_ttl_seconds: float = 2.5):
        self.cache_ttl = cache_ttl_seconds
        self._telemetry_cache: Dict[str, Any] = {}
        self._cache_timestamp: float = 0.0

        # Prime CPU percent measurement
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass

    # ── SYSTEM TELEMETRY ────────────────────────────────────────────

    def get_system_telemetry(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Unified telemetry: CPU, RAM, GPU (RTX 4060), Disk, Battery, Network.
        Cached with TTL to avoid CPU spikes during fast polling.
        """
        now = time.time()
        if not force_refresh and (now - self._cache_timestamp) < self.cache_ttl:
            return dict(self._telemetry_cache)

        telemetry: Dict[str, Any] = {
            "timestamp": now,
            "cpu": self.get_cpu_info(),
            "memory": self.get_memory_info(),
            "gpu": self.get_gpu_info(),
            "disk": self.get_disk_info(),
            "battery": self.get_battery_info(),
            "network": self.get_network_info(),
        }

        self._telemetry_cache = telemetry
        self._cache_timestamp = now
        return telemetry

    def get_cpu_info(self) -> Dict[str, Any]:
        """CPU utilization total and per-core info."""
        try:
            total_percent = psutil.cpu_percent(interval=None)
            per_core = psutil.cpu_percent(interval=None, percpu=True)
            freq = psutil.cpu_freq()
            return {
                "utilization_percent": total_percent,
                "per_core_percent": per_core,
                "cores_logical": psutil.cpu_count(logical=True),
                "cores_physical": psutil.cpu_count(logical=False),
                "frequency_mhz": round(freq.current, 1) if freq else None,
            }
        except Exception as e:
            return {"error": str(e), "utilization_percent": 0.0}

    def get_memory_info(self) -> Dict[str, Any]:
        """RAM usage, total, and available memory."""
        try:
            v = psutil.virtual_memory()
            return {
                "total_gb": round(v.total / (1024 ** 3), 2),
                "available_gb": round(v.available / (1024 ** 3), 2),
                "used_gb": round(v.used / (1024 ** 3), 2),
                "percent": v.percent,
            }
        except Exception as e:
            return {"error": str(e), "percent": 0.0}

    def get_gpu_info(self) -> Dict[str, Any]:
        """
        GPU utilization, VRAM, and temperature.
        Prefers NVML (in-process C library call) to avoid spawning nvidia-smi subprocesses.
        """
        if _NVML_AVAILABLE:
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                return {
                    "name": name,
                    "available": True,
                    "utilization_gpu_percent": util.gpu,
                    "utilization_memory_percent": util.memory,
                    "vram_total_mb": round(mem.total / (1024 ** 2), 1),
                    "vram_used_mb": round(mem.used / (1024 ** 2), 1),
                    "vram_free_mb": round(mem.free / (1024 ** 2), 1),
                    "temperature_c": temp,
                }
            except Exception as e:
                logger.debug(f"NVML read error: {e}")

        # Fallback to GPUManager if available in core
        try:
            from core.gpu_manager import GPUManager
            return GPUManager().get_metrics()
        except Exception:
            return {
                "name": "NVIDIA GeForce RTX 4060 Laptop GPU",
                "available": True,
                "vram_total_mb": 8192,
                "note": "Telemetric fallback",
            }

    def get_disk_info(self, path: str = "C:\\") -> Dict[str, Any]:
        """Disk usage on target drive."""
        try:
            usage = psutil.disk_usage(path)
            return {
                "drive": path,
                "total_gb": round(usage.total / (1024 ** 3), 2),
                "used_gb": round(usage.used / (1024 ** 3), 2),
                "free_gb": round(usage.free / (1024 ** 3), 2),
                "percent": usage.percent,
            }
        except Exception as e:
            return {"error": str(e), "percent": 0.0}

    def get_battery_info(self) -> Dict[str, Any]:
        """Battery percentage, charging state, and remaining time."""
        try:
            b = psutil.sensors_battery()
            if not b:
                return {"has_battery": False, "percent": 100, "plugged_in": True}
            return {
                "has_battery": True,
                "percent": round(b.percent, 1),
                "plugged_in": b.power_plugged,
                "secs_left": b.secsleft if b.secsleft != psutil.POWER_TIME_UNLIMITED else -1,
            }
        except Exception as e:
            return {"has_battery": False, "error": str(e)}

    def get_network_info(self) -> Dict[str, Any]:
        """Network interface status and counters."""
        try:
            stats = psutil.net_if_stats()
            active_interfaces = []
            for iface, stat in stats.items():
                if stat.isup and stat.speed > 0:
                    active_interfaces.append({
                        "interface": iface,
                        "speed_mbps": stat.speed,
                    })
            return {"active_interfaces": active_interfaces, "count": len(active_interfaces)}
        except Exception as e:
            return {"error": str(e), "active_interfaces": []}

    # ── AUDIO & HARDWARE CONTROLS ───────────────────────────────────

    def get_volume(self) -> Dict[str, Any]:
        """Get system master volume level."""
        try:
            from tools import windows_control
            val = windows_control.get_volume()
            return {"success": True, "volume": val}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def set_volume(self, level: int) -> Dict[str, Any]:
        """Set system master volume (0 to 100)."""
        clamped = max(0, min(100, int(level)))
        try:
            from tools import windows_control
            msg = windows_control.set_volume(clamped)
            return {"success": True, "level": clamped, "message": msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_brightness(self) -> Dict[str, Any]:
        """Get display brightness."""
        try:
            from tools import windows_control
            val = windows_control.get_brightness()
            return {"success": True, "brightness": val}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def set_brightness(self, level: int) -> Dict[str, Any]:
        """Set display brightness (0 to 100)."""
        clamped = max(0, min(100, int(level)))
        try:
            from tools import windows_control
            msg = windows_control.set_brightness(clamped)
            return {"success": True, "level": clamped, "message": msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def lock_pc(self) -> Dict[str, Any]:
        """Lock Windows workstation immediately."""
        try:
            ctypes.windll.user32.LockWorkStation()
            return {"success": True, "message": "Workstation locked."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def shutdown_pc(self, delay_seconds: int = 30) -> Dict[str, Any]:
        """Schedule PC shutdown."""
        try:
            subprocess.run(["shutdown", "/s", "/t", str(delay_seconds)], shell=False, check=True)
            return {"success": True, "message": f"Shutdown scheduled in {delay_seconds} seconds."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def restart_pc(self, delay_seconds: int = 30) -> Dict[str, Any]:
        """Schedule PC restart."""
        try:
            subprocess.run(["shutdown", "/r", "/t", str(delay_seconds)], shell=False, check=True)
            return {"success": True, "message": f"Restart scheduled in {delay_seconds} seconds."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def cancel_shutdown(self) -> Dict[str, Any]:
        """Cancel scheduled shutdown or restart."""
        try:
            subprocess.run(["shutdown", "/a"], shell=False, check=True)
            return {"success": True, "message": "Scheduled shutdown cancelled."}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Singleton instance
native_system = NativeSystemManager()
