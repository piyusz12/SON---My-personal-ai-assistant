# plugins/windows.py — Windows Desktop & System Control Plugin for SON V3
import os
import ctypes
import subprocess
from pathlib import Path
from core.config import SecurityLevel, Config
from plugins.base import BasePlugin

APP_MAP = {
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "chrome": "start chrome",
    "google chrome": "start chrome",
    "firefox": "start firefox",
    "edge": "start msedge",
    "notepad": "notepad",
    "explorer": "explorer",
    "file explorer": "explorer",
    "calculator": "calc",
    "terminal": "wt",
    "windows terminal": "wt",
    "cmd": "cmd",
    "powershell": "powershell",
    "spotify": "start spotify:",
    "steam": "start steam://open/main",
    "discord": "start discord:",
    "task manager": "taskmgr",
    "settings": "start ms-settings:",
    "paint": "mspaint",
    "downloads": f'explorer "{Path.home() / "Downloads"}"',
    "documents": f'explorer "{Path.home() / "Documents"}"',
}


class WindowsPlugin(BasePlugin):
    """
    Manages Windows desktop windows, app execution, and system hardware controls.
    """

    def __init__(self):
        super().__init__(name="windows", description="Windows application, window, and hardware manager", category="system")

    def initialize(self):
        # Application Controls
        self.register_tool(
            "open_application", self.open_application,
            description="Open a desktop application by name (e.g. 'VS Code', 'Chrome', 'Spotify', 'Downloads')",
            params={"name": {"type": "string", "description": "Application or workspace name"}},
            required=["name"], security_level=SecurityLevel.SAFE
        )
        self.register_tool(
            "close_application", self.close_application,
            description="Close a running application by name",
            params={"name": {"type": "string", "description": "Application name"}},
            required=["name"], security_level=SecurityLevel.MEDIUM
        )

        # Window State Controls
        self.register_tool(
            "minimize_window", self.minimize_window,
            description="Minimize a window by title",
            params={"title": {"type": "string", "description": "Window title keyword"}},
            required=["title"], security_level=SecurityLevel.SAFE
        )
        self.register_tool(
            "maximize_window", self.maximize_window,
            description="Maximize a window by title",
            params={"title": {"type": "string", "description": "Window title keyword"}},
            required=["title"], security_level=SecurityLevel.SAFE
        )
        self.register_tool(
            "snap_window", self.snap_window,
            description="Snap a window to left or right half of screen",
            params={
                "title": {"type": "string", "description": "Window title keyword"},
                "position": {"type": "string", "enum": ["left", "right"], "description": "Snap target position"}
            },
            required=["title", "position"], security_level=SecurityLevel.SAFE
        )

        # Hardware & System
        self.register_tool(
            "set_volume", self.set_volume,
            description="Set master volume (0 to 100)",
            params={"level": {"type": "integer", "description": "Volume percentage"}},
            required=["level"], security_level=SecurityLevel.SAFE
        )
        self.register_tool(
            "set_brightness", self.set_brightness,
            description="Set screen brightness (0 to 100)",
            params={"level": {"type": "integer", "description": "Brightness percentage"}},
            required=["level"], security_level=SecurityLevel.SAFE
        )
        self.register_tool(
            "get_system_info", self.get_system_info,
            description="Get CPU, GPU, RAM, Disk, and battery status",
            params={}, security_level=SecurityLevel.SAFE
        )
        self.register_tool(
            "lock_pc", self.lock_pc,
            description="Lock the workstation",
            params={}, security_level=SecurityLevel.SAFE
        )
        self.register_tool(
            "shutdown_pc", self.shutdown_pc,
            description="Schedule PC shutdown",
            params={"delay_seconds": {"type": "integer", "default": 30}},
            security_level=SecurityLevel.CRITICAL
        )
        self.register_tool(
            "restart_pc", self.restart_pc,
            description="Schedule PC restart",
            params={"delay_seconds": {"type": "integer", "default": 30}},
            security_level=SecurityLevel.CRITICAL
        )

    # ── Tool Implementations ──────────────────────────────────

    def open_application(self, name: str) -> str:
        key = name.strip().lower()
        cmd = APP_MAP.get(key, f"start {name}")
        try:
            subprocess.Popen(cmd, shell=True)
            return f"Opened '{name}'."
        except Exception as e:
            return f"Failed to open '{name}': {e}"

    def close_application(self, name: str) -> str:
        import psutil
        target = name.strip().lower()
        killed = 0
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] and target in proc.info["name"].lower():
                    proc.terminate()
                    killed += 1
            except Exception:
                pass
        return f"Closed {killed} instance(s) of '{name}'." if killed else f"No running app found for '{name}'."

    def _find_window(self, title: str):
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(title)
            return wins[0] if wins else None
        except Exception:
            return None

    def minimize_window(self, title: str) -> str:
        win = self._find_window(title)
        if win:
            win.minimize()
            return f"Minimized window '{win.title}'."
        return f"Window matching '{title}' not found."

    def maximize_window(self, title: str) -> str:
        win = self._find_window(title)
        if win:
            win.maximize()
            return f"Maximized window '{win.title}'."
        return f"Window matching '{title}' not found."

    def snap_window(self, title: str, position: str) -> str:
        win = self._find_window(title)
        if not win:
            return f"Window matching '{title}' not found."

        try:
            # Calculate native screen dimensions via Win32 API
            screen_w = ctypes.windll.user32.GetSystemMetrics(0)
            screen_h = ctypes.windll.user32.GetSystemMetrics(1)
            half_w = screen_w // 2

            win.restore()
            if position == "left":
                win.moveTo(0, 0)
                win.resizeTo(half_w, screen_h)
            else:
                win.moveTo(half_w, 0)
                win.resizeTo(half_w, screen_h)
            return f"Snapped '{win.title}' to the {position}."
        except Exception as e:
            return f"Failed to snap window: {e}"

    def set_volume(self, level: int) -> str:
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            from ctypes import cast, POINTER

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            lvl = max(0, min(100, int(level)))
            volume.SetMasterVolumeLevelScalar(lvl / 100.0, None)
            return f"Volume set to {lvl}%."
        except Exception as e:
            return f"Could not set volume: {e}"

    def set_brightness(self, level: int) -> str:
        try:
            import screen_brightness_control as sbc
            lvl = max(0, min(100, int(level)))
            sbc.set_brightness(lvl)
            return f"Brightness set to {lvl}%."
        except Exception as e:
            return f"Could not set brightness: {e}"

    def get_system_info(self) -> str:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")

        info = [
            f"CPU Usage: {cpu}%",
            f"RAM Usage: {ram.used / (1024**3):.1f} / {ram.total / (1024**3):.1f} GB ({ram.percent}%)",
            f"Disk (C:): {disk.used / (1024**3):.1f} / {disk.total / (1024**3):.1f} GB ({disk.percent}%)"
        ]

        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if res.returncode == 0:
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                info.append(f"GPU: {parts[0]} — {parts[1]}% util, {parts[2]}/{parts[3]} MB VRAM")
        except Exception:
            pass

        return "\n".join(info)

    def lock_pc(self) -> str:
        ctypes.windll.user32.LockWorkStation()
        return "Workstation locked."

    def shutdown_pc(self, delay_seconds: int = 30) -> str:
        subprocess.Popen(f"shutdown /s /t {delay_seconds}", shell=True)
        return f"PC shutdown scheduled in {delay_seconds} seconds."

    def restart_pc(self, delay_seconds: int = 30) -> str:
        subprocess.Popen(f"shutdown /r /t {delay_seconds}", shell=True)
        return f"PC restart scheduled in {delay_seconds} seconds."
