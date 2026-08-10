import ctypes
import subprocess
import re
from pathlib import Path
from core.config import SecurityLevel
from plugins.base import BasePlugin
import logging
from core.config import Config
logger = Config.get_logger(__name__)


# Whitelisted applications - only these can be launched
APP_MAP = {
    "vscode": ["code"],
    "vs code": ["code"],
    "visual studio code": ["code"],
    "chrome": ["C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"],
    "google chrome": ["C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"],
    "firefox": ["C:\\Program Files\\Mozilla Firefox\\firefox.exe"],
    "edge": ["C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"],
    "notepad": ["notepad.exe"],
    "explorer": ["explorer.exe"],
    "file explorer": ["explorer.exe"],
    "calculator": ["calc.exe"],
    "terminal": ["wt.exe"],
    "windows terminal": ["wt.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "spotify": ["C:\\Users\\%USERNAME%\\AppData\\Roaming\\Spotify\\Spotify.exe"],
    "steam": ["C:\\Program Files (x86)\\Steam\\steam.exe"],
    "discord": ["C:\\Users\\%USERNAME%\\AppData\\Local\\Discord\\app-*\\Discord.exe"],
    "task manager": ["taskmgr.exe"],
    "settings": ["SystemSettings.exe"],
    "paint": ["mspaint.exe"],
}

# Safe folder paths
SAFE_FOLDERS = {
    "downloads": lambda: str(Path.home() / "Downloads"),
    "documents": lambda: str(Path.home() / "Documents"),
    "desktop": lambda: str(Path.home() / "Desktop"),
    "pictures": lambda: str(Path.home() / "Pictures"),
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
        """Open a whitelisted application by name."""
        key = name.strip().lower()
        
        # Check for safe folder shortcuts
        if key in SAFE_FOLDERS:
            try:
                folder_path = SAFE_FOLDERS[key]()
                subprocess.Popen(["explorer.exe", folder_path], shell=False)
                return f"Opened {name} folder."
            except Exception as e:
                return f"Failed to open {name} folder: {e}"
        
        # Check whitelisted apps
        if key not in APP_MAP:
            return f"Application '{name}' is not in the whitelist. Available apps: {', '.join(APP_MAP.keys())}"
        
        cmd = APP_MAP[key]
        try:
            # Expand environment variables in path
            cmd_expanded = [arg.replace("%USERNAME%", Path.home().name) for arg in cmd]
            
            # Use shell=False for security - no command injection possible
            subprocess.Popen(cmd_expanded, shell=False)
            return f"Opened '{name}'."
        except FileNotFoundError:
            return f"Application '{name}' not found at expected path."
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
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception as e:
                logger.warning(f"Error terminating process: {e}")
        return f"Closed {killed} instance(s) of '{name}'." if killed else f"No running app found for '{name}'."

    def _find_window(self, title: str):
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(title)
            return wins[0] if wins else None
        except Exception as e:
            logger.debug(f"Window search failed for '{title}': {e}")
            return None

    def minimize_window(self, title: str) -> str:
        win = self._find_window(title)
        if win:
            try:
                win.minimize()
                return f"Minimized window '{win.title}'."
            except Exception as e:
                return f"Could not minimize window: {e}"
        return f"Window matching '{title}' not found."

    def maximize_window(self, title: str) -> str:
        win = self._find_window(title)
        if win:
            try:
                win.maximize()
                return f"Maximized window '{win.title}'."
            except Exception as e:
                return f"Could not maximize window: {e}"
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
            import comtypes
            comtypes.CoInitialize()
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
            finally:
                try:
                    comtypes.CoUninitialize()
                except Exception:
                    pass
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
            from core.gpu_manager import GPUManager
            gpu_metrics = GPUManager().get_metrics()
            info.append(f"GPU: {gpu_metrics.get('gpu_name', 'NVIDIA GPU')} — {gpu_metrics.get('gpu_util', 0)}% util, {gpu_metrics.get('vram_used_mb', 0):.0f}/{gpu_metrics.get('vram_total_mb', 0):.0f} MB VRAM")
        except Exception as e:
            logger.debug(f"GPU metrics fetch error: {e}")

        return "\n".join(info)

    def lock_pc(self) -> str:
        ctypes.windll.user32.LockWorkStation()
        return "Workstation locked."

    def shutdown_pc(self, delay_seconds: int = 30) -> str:
        """Schedule PC shutdown with confirmation."""
        import os
        # Check for environment variable to bypass confirmation (for automation)
        if not os.environ.get("SON_BYPASS_CONFIRMATION"):
            return "Shutdown requires confirmation. Use 'shutdown /s /t <seconds>' manually or set SON_BYPASS_CONFIRMATION=1."
        
        delay = max(0, int(delay_seconds))
        try:
            subprocess.Popen(["shutdown", "/s", "/t", str(delay)], shell=False)
            return f"PC shutdown scheduled in {delay} seconds. Run 'shutdown /a' to cancel."
        except Exception as e:
            return f"Failed to schedule shutdown: {e}"

    def restart_pc(self, delay_seconds: int = 30) -> str:
        """Schedule PC restart with confirmation."""
        import os
        # Check for environment variable to bypass confirmation (for automation)
        if not os.environ.get("SON_BYPASS_CONFIRMATION"):
            return "Restart requires confirmation. Use 'shutdown /r /t <seconds>' manually or set SON_BYPASS_CONFIRMATION=1."
        
        delay = max(0, int(delay_seconds))
        try:
            subprocess.Popen(["shutdown", "/r", "/t", str(delay)], shell=False)
            return f"PC restart scheduled in {delay} seconds. Run 'shutdown /a' to cancel."
        except Exception as e:
            return f"Failed to schedule restart: {e}"
