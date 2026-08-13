# core/health.py — Service Health Monitor for SON V3
"""
Periodically checks all services and exposes a health dashboard.

SON STATUS
──────────────
Brain       ONLINE  🟢
Voice       ONLINE  🟢
Memory      ONLINE  🟢
Vision      OFFLINE 🔴
Docker      ONLINE  🟢
GPU         62%
VRAM        5.8 GB / 8.0 GB

Usage:
    from core.health import HealthMonitor

    monitor = HealthMonitor()
    monitor.start(interval=10.0)

    status = monitor.get_status()
    print(monitor.format_dashboard())
"""
import time
import threading
import json
import logging
from dataclasses import dataclass, field
from enum import Enum

from core.config import Config

logger = Config.get_logger(__name__)


class ServiceStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class ServiceHealth:
    """Health state of a single service."""
    name: str
    status: ServiceStatus = ServiceStatus.UNKNOWN
    latency_ms: float = 0.0
    details: str = ""
    last_checked: float = 0.0
    consecutive_failures: int = 0


class HealthMonitor:
    """
    Monitors all SON services and provides a unified health view.

    Services monitored:
    - Ollama (LLM brain)
    - GPU (utilization, VRAM, temperature)
    - Microphone (audio input)
    - TTS (text-to-speech model)
    - ChromaDB (vector memory)
    - Docker (container runtime)
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._services: dict[str, ServiceHealth] = {
            "ollama": ServiceHealth(name="Ollama (Brain)"),
            "gpu": ServiceHealth(name="GPU"),
            "microphone": ServiceHealth(name="Microphone"),
            "tts": ServiceHealth(name="TTS Engine"),
            "chromadb": ServiceHealth(name="ChromaDB (Memory)"),
            "docker": ServiceHealth(name="Docker"),
            "camera": ServiceHealth(name="Camera (Vision)"),
        }
        self._monitoring = False
        self._monitor_thread: threading.Thread | None = None
        self._gpu_metrics: dict = {}

    def start(self, interval: float = 10.0):
        """Start background health monitoring."""
        if self._monitoring:
            return
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True,
            name="HealthMonitor",
        )
        self._monitor_thread.start()
        logger.info(f"Health monitor started (interval: {interval}s)")

    def start_monitoring(self, interval: float = 10.0):
        """Alias for start()."""
        self.start(interval=interval)

    def stop(self):
        """Stop monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)

    def stop_monitoring(self):
        """Alias for stop()."""
        self.stop()

    def check_all(self):
        """Run a single pass of all service checks synchronously."""
        self._check_ollama()
        self._check_gpu()
        self._check_microphone()
        self._check_chromadb()
        self._check_docker()
        self._check_camera()

    def _monitor_loop(self, interval: float):
        """Background loop that checks all services."""
        while self._monitoring:
            try:
                self.check_all()
                # TTS is checked on-demand (model may not be loaded yet)
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
            time.sleep(interval)

    def _check_camera(self):
        """Check Camera Subsystem and Privacy Gate status."""
        try:
            from vision.camera.capture import CameraManager
            cam = CameraManager()
            status = cam.get_privacy_status()
            if status["camera_active"]:
                st = ServiceStatus.ONLINE if status["hardware_running"] else ServiceStatus.ONLINE
                det = "ON" if status["person_detection_enabled"] else "OFF"
                rec = "ON" if status["face_recognition_enabled"] else "OFF"
                self._update_service("camera", st, 0, f"Active | Det: {det} | Rec: {rec}")
            else:
                self._update_service("camera", ServiceStatus.OFFLINE, 0, "Paused for privacy")
        except Exception as e:
            self._update_service("camera", ServiceStatus.UNKNOWN, 0, str(e))

    # ── Individual Service Checks ────────────────────────────────

    def _check_ollama(self):
        """Check Ollama connectivity."""
        import urllib.request
        start = time.perf_counter()
        try:
            req = urllib.request.Request(f"{Config.OLLAMA_HOST}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                latency = (time.perf_counter() - start) * 1000
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    models = [m.get("name", "") for m in data.get("models", [])]
                    self._update_service("ollama", ServiceStatus.ONLINE, latency,
                                         f"{len(models)} models available")
                else:
                    self._update_service("ollama", ServiceStatus.DEGRADED, latency,
                                         f"HTTP {resp.status}")
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            self._update_service("ollama", ServiceStatus.OFFLINE, latency, str(e))

    def _check_gpu(self):
        """Check GPU status via pynvml."""
        try:
            from core.gpu_manager import GPUManager
            gpu = GPUManager()
            metrics = gpu.get_metrics()
            self._gpu_metrics = metrics

            vram_pct = (metrics["vram_used_mb"] / metrics["vram_total_mb"] * 100) if metrics["vram_total_mb"] > 0 else 0
            temp = metrics.get("gpu_temp_c", 0)

            if temp > 90:
                status = ServiceStatus.DEGRADED
                details = f"HIGH TEMP: {temp}°C"
            elif vram_pct > 95:
                status = ServiceStatus.DEGRADED
                details = f"VRAM nearly full: {vram_pct:.0f}%"
            else:
                status = ServiceStatus.ONLINE
                details = (
                    f"Util: {metrics['gpu_util']:.0f}% | "
                    f"VRAM: {metrics['vram_used_mb']:.0f}/{metrics['vram_total_mb']:.0f} MB | "
                    f"Temp: {temp:.0f}°C"
                )

            self._update_service("gpu", status, 0, details)

        except ImportError:
            self._update_service("gpu", ServiceStatus.UNKNOWN, 0, "pynvml not available")
        except Exception as e:
            self._update_service("gpu", ServiceStatus.UNKNOWN, 0, str(e))

    def _check_microphone(self):
        """Check if microphone is available."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            default_input = sd.default.device[0]
            if default_input is not None and default_input >= 0:
                dev_name = devices[default_input]["name"]
                self._update_service("microphone", ServiceStatus.ONLINE, 0, dev_name)
            else:
                self._update_service("microphone", ServiceStatus.OFFLINE, 0, "No input device")
        except ImportError:
            self._update_service("microphone", ServiceStatus.UNKNOWN, 0, "sounddevice not installed")
        except Exception as e:
            self._update_service("microphone", ServiceStatus.OFFLINE, 0, str(e))

    def _check_chromadb(self):
        """Check ChromaDB accessibility."""
        start = time.perf_counter()
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(Config.MEMORY_DIR))
            # Quick heartbeat — list collections
            collections = client.list_collections()
            latency = (time.perf_counter() - start) * 1000
            self._update_service("chromadb", ServiceStatus.ONLINE, latency,
                                 f"{len(collections)} collections")
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            self._update_service("chromadb", ServiceStatus.OFFLINE, latency, str(e))

    def _check_docker(self):
        """Check Docker daemon."""
        try:
            import docker as docker_sdk
            client = docker_sdk.from_env()
            client.ping()
            containers = client.containers.list()
            self._update_service("docker", ServiceStatus.ONLINE, 0,
                                 f"{len(containers)} running")
        except Exception:
            try:
                import subprocess
                res = subprocess.run(["docker", "info"], capture_output=True, timeout=2)
                if res.returncode == 0:
                    self._update_service("docker", ServiceStatus.ONLINE, 0, "via CLI")
                else:
                    self._update_service("docker", ServiceStatus.OFFLINE, 0, "Daemon not running")
            except Exception:
                self._update_service("docker", ServiceStatus.OFFLINE, 0, "Not installed or not running")

    def check_tts(self, tts_module=None):
        """Check TTS model status (called externally since TTS is lazy-loaded)."""
        if tts_module and hasattr(tts_module, "is_loaded") and tts_module.is_loaded:
            gpu_str = " (GPU)" if getattr(tts_module, "using_gpu", False) else " (CPU)"
            self._update_service("tts", ServiceStatus.ONLINE, 0, f"Piper loaded{gpu_str}")
        else:
            self._update_service("tts", ServiceStatus.OFFLINE, 0, "Not loaded")

    # ── State Management ─────────────────────────────────────────

    def _update_service(self, name: str, status: ServiceStatus, latency_ms: float, details: str):
        """Update a service's health status."""
        with self._lock:
            svc = self._services.get(name)
            if svc:
                if status != ServiceStatus.ONLINE:
                    svc.consecutive_failures += 1
                else:
                    svc.consecutive_failures = 0
                svc.status = status
                svc.latency_ms = round(latency_ms, 1)
                svc.details = details
                svc.last_checked = time.time()

    # ── Query Methods ────────────────────────────────────────────

    def get_status(self) -> dict:
        """Get full health status as a dict."""
        with self._lock:
            result = {}
            for name, svc in self._services.items():
                result[name] = {
                    "name": svc.name,
                    "status": svc.status.value,
                    "latency_ms": svc.latency_ms,
                    "details": svc.details,
                    "consecutive_failures": svc.consecutive_failures,
                }
            return result

    def is_all_healthy(self) -> bool:
        """Check if all critical services are online."""
        critical = ["ollama", "gpu", "chromadb"]
        with self._lock:
            return all(
                self._services[s].status == ServiceStatus.ONLINE
                for s in critical
                if s in self._services
            )

    def get_gpu_metrics(self) -> dict:
        """Get cached GPU metrics."""
        return self._gpu_metrics.copy()

    def format_dashboard(self) -> str:
        """
        Format a human-readable health dashboard.

        SON STATUS
        ──────────────────────────────────────
        Ollama (Brain)     ONLINE   🟢  3.2ms
        GPU                ONLINE   🟢  Util: 42% | VRAM: 5.8/8.0 GB
        Microphone         ONLINE   🟢  Realtek HD Audio
        TTS Engine         ONLINE   🟢  Piper loaded (CPU)
        ChromaDB (Memory)  ONLINE   🟢  3 collections
        Docker             OFFLINE  🔴  Daemon not running
        """
        status_icons = {
            ServiceStatus.ONLINE: "🟢",
            ServiceStatus.OFFLINE: "🔴",
            ServiceStatus.DEGRADED: "🟡",
            ServiceStatus.UNKNOWN: "⚪",
        }

        lines = [
            "SON STATUS",
            "─" * 60,
        ]

        with self._lock:
            for name, svc in self._services.items():
                icon = status_icons.get(svc.status, "⚪")
                status_str = svc.status.value.upper()
                latency_str = f"{svc.latency_ms:.0f}ms" if svc.latency_ms > 0 else ""

                detail_parts = []
                if latency_str:
                    detail_parts.append(latency_str)
                if svc.details:
                    detail_parts.append(svc.details)
                detail_str = "  ".join(detail_parts)

                lines.append(
                    f"  {svc.name:<20s} {status_str:<10s} {icon}  {detail_str}"
                )

        return "\n".join(lines)
