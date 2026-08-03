# core/state.py — Real-time System State Monitor for SON V3
import time
import threading
import urllib.request
from typing import Callable, Any
from core.config import Config


class SystemState:
    """
    Central state container and telemetry monitor for SON V3.
    Tracks CPU/GPU/RAM metrics, active services, voice state, and notifications.
    """

    def __init__(self):
        self._lock = threading.Lock()

        # Telemetry
        self.cpu_percent: float = 0.0
        self.ram_percent: float = 0.0
        self.ram_used_gb: float = 0.0
        self.ram_total_gb: float = 0.0
        self.gpu_name: str = "NVIDIA GeForce RTX 4060 Laptop GPU"
        self.gpu_util: float = 0.0
        self.gpu_vram_used_mb: float = 0.0
        self.gpu_vram_total_mb: float = 8188.0
        self.gpu_temp_c: float = 0.0

        # Services status
        self.ollama_online: bool = False
        self.ollama_running_model: str = ""
        self.docker_online: bool = False
        self.docker_containers_running: int = 0

        # Voice state
        self.is_listening: bool = False
        self.is_speaking: bool = False
        self.is_thinking: bool = False
        self.wakeword_active: bool = False

        # System notifications queue
        self.notifications: list[dict] = []
        self._listeners: list[Callable[[str, Any], None]] = []

        # Background monitoring thread
        self._monitoring = False
        self._monitor_thread = None

    def start_monitoring(self, interval: float = 2.0):
        """Start background telemetry monitoring thread."""
        if self._monitoring:
            return
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True,
            name="SystemStateMonitor"
        )
        self._monitor_thread.start()

    def stop_monitoring(self):
        self._monitoring = False

    def _monitor_loop(self, interval: float):
        import psutil

        while self._monitoring:
            try:
                # CPU & RAM
                c_pct = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory()

                with self._lock:
                    self.cpu_percent = c_pct
                    self.ram_percent = ram.percent
                    self.ram_used_gb = round(ram.used / (1024**3), 1)
                    self.ram_total_gb = round(ram.total / (1024**3), 1)

                # GPU metrics via nvidia-smi
                self._update_gpu_metrics()

                # Check Ollama & Docker status
                self._update_services_status()

                # Notify listeners
                self._emit_change("telemetry_update", self.get_summary())

            except Exception:
                pass

            time.sleep(interval)

    def _update_gpu_metrics(self):
        import subprocess
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if res.returncode == 0:
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                if len(parts) >= 4:
                    with self._lock:
                        self.gpu_util = float(parts[0])
                        self.gpu_vram_used_mb = float(parts[1])
                        self.gpu_vram_total_mb = float(parts[2])
                        self.gpu_temp_c = float(parts[3])
        except Exception:
            pass

    def _update_services_status(self):
        import json

        # Ollama check
        try:
            req = urllib.request.Request(f"{Config.OLLAMA_HOST}/api/ps")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    models = data.get("models", [])
                    with self._lock:
                        self.ollama_online = True
                        self.ollama_running_model = models[0]["name"] if models else "None"
        except Exception:
            with self._lock:
                self.ollama_online = False
                self.ollama_running_model = "Offline"

        # Docker check
        import subprocess
        try:
            res = subprocess.run(["docker", "info"], capture_output=True, timeout=2)
            with self._lock:
                self.docker_online = (res.returncode == 0)
        except Exception:
            with self._lock:
                self.docker_online = False

    def add_notification(self, title: str, message: str, level: str = "info"):
        """Add a notification to the history queue."""
        item = {
            "title": title,
            "message": message,
            "level": level,
            "timestamp": time.strftime("%H:%M:%S")
        }
        with self._lock:
            self.notifications.append(item)
            if len(self.notifications) > 50:
                self.notifications.pop(0)
        self._emit_change("notification", item)

    def subscribe(self, listener: Callable[[str, Any], None]):
        """Subscribe to state change events."""
        with self._lock:
            self._listeners.append(listener)

    def _emit_change(self, event: str, data: Any):
        for listener in list(self._listeners):
            try:
                listener(event, data)
            except Exception:
                pass

    def get_summary(self) -> dict:
        with self._lock:
            return {
                "cpu_percent": self.cpu_percent,
                "ram_percent": self.ram_percent,
                "ram_used_gb": self.ram_used_gb,
                "ram_total_gb": self.ram_total_gb,
                "gpu_name": self.gpu_name,
                "gpu_util": self.gpu_util,
                "gpu_vram_used_mb": self.gpu_vram_used_mb,
                "gpu_vram_total_mb": self.gpu_vram_total_mb,
                "gpu_temp_c": self.gpu_temp_c,
                "ollama_online": self.ollama_online,
                "ollama_model": self.ollama_running_model,
                "docker_online": self.docker_online,
                "is_listening": self.is_listening,
                "is_speaking": self.is_speaking,
                "is_thinking": self.is_thinking,
            }
