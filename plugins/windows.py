# plugins/windows.py — Windows Management Plugin for SON V3
"""
Windows Management Plugin for SON V3.
Delegates all application lifecycle, window management, volume, brightness,
and system controls directly to tools.windows_control.
"""
from pathlib import Path
import psutil
from core.config import SecurityLevel, Config
from plugins.base import BasePlugin
from tools import windows_control

logger = Config.get_logger(__name__)

# Backward-compatible references
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
        # Prime CPU percent measurement for non-blocking telemetry calls
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass

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
        self.register_tool(
            "create_office_document", self.create_office_document,
            description="Create a formatted Microsoft Word (.docx) document (e.g. leave application, letter, notes) and automatically open it in Microsoft Office Word",
            params={
                "filename": {"type": "string", "description": "Filename ending with .docx (e.g. 'Leave_Application.docx')", "default": "leave_letter.docx"},
                "content": {"type": "string", "description": "The complete formatted text or letter content to write"},
                "title": {"type": "string", "description": "Document title heading", "default": "Leave Application"},
                "open_after": {"type": "boolean", "description": "Whether to automatically open in Microsoft Office Word", "default": True},
            },
            required=["content"], security_level=SecurityLevel.SAFE
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

        # Message Typing & Automation
        self.register_tool(
            "type_message", self.type_message,
            description="Type a message on behalf of Dad into any web app (WhatsApp, Discord, Slack, ChatGPT) or open window, optionally sending it",
            params={
                "message": {"type": "string", "description": "The exact message to type"},
                "app_name_or_title": {"type": "string", "description": "Target app or window name (e.g. 'whatsapp', 'discord', 'slack', 'chrome', 'opera', or '' for active)", "default": ""},
                "press_enter": {"type": "boolean", "description": "Whether to press Enter after typing to send the message", "default": False},
            },
            required=["message"], security_level=SecurityLevel.MEDIUM
        )
        self.register_tool(
            "list_open_windows", self.list_open_windows,
            description="List all currently open windows and web applications",
            params={"query": {"type": "string", "description": "Optional title filter", "default": ""}},
            security_level=SecurityLevel.SAFE
        )

    # ── Tool Implementations (Delegating to tools.windows_control) ────

    def open_application(self, name: str) -> str:
        key = name.strip().lower()
        if key in SAFE_FOLDERS:
            try:
                folder_path = SAFE_FOLDERS[key]()
                return windows_control.open_folder(folder_path)
            except Exception as e:
                return f"Failed to open {name} folder: {e}"
        res = windows_control.open_application(name)
        if key == "discord" and res == "Opened discord.":
            return "Opened 'discord'."
        return res

    def close_application(self, name: str) -> str:
        return windows_control.close_application(name)

    def create_office_document(self, content: str, filename: str = "leave_letter.docx", title: str = "Leave Application", open_after: bool = True) -> str:
        return windows_control.create_office_document(filename=filename, content=content, title=title, open_after=open_after)

    def minimize_window(self, title: str) -> str:
        return windows_control.minimize_window(title)

    def maximize_window(self, title: str) -> str:
        return windows_control.maximize_window(title)

    def snap_window(self, title: str, position: str) -> str:
        return windows_control.snap_window(title, position)

    def set_volume(self, level: int) -> str:
        return windows_control.set_volume(level)

    def set_brightness(self, level: int) -> str:
        return windows_control.set_brightness(level)

    def get_system_info(self) -> str:
        return windows_control.get_system_info()

    def lock_pc(self) -> str:
        return windows_control.lock_pc()

    def shutdown_pc(self, delay_seconds: int = 30) -> str:
        return windows_control.shutdown_pc(delay_seconds)

    def restart_pc(self, delay_seconds: int = 30) -> str:
        return windows_control.restart_pc(delay_seconds)

    def type_message(self, message: str, app_name_or_title: str = "", press_enter: bool = False) -> str:
        blocked_terminals = ["cmd", "powershell", "terminal", "bash", "wt.exe", "conhost", "sh.exe"]
        target_lower = (app_name_or_title or "").lower()
        if press_enter and any(t in target_lower for t in blocked_terminals):
            return "Security Error: Automated keystroke submission (Enter) to command terminals is blocked for system safety."
        return windows_control.type_message(message=message, app_name_or_title=app_name_or_title, press_enter=press_enter)

    def list_open_windows(self, query: str = "") -> str:
        return windows_control.list_open_windows(query=query)
