# core/execution/tier1_native/windows.py — Tier 1 Native Windows Window Management
"""
Direct native Win32 window management using ctypes and user32.dll.
Supports window enumeration, focus, state manipulation (minimize, maximize, restore),
and screen snapping with UIPI respect.
"""
import ctypes
from ctypes import wintypes
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32

# Win32 Constants
SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_MAXIMIZE = 3
SW_SHOWNOACTIVATE = 4
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040

HWND_TOP = 0

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class NativeWindowManager:
    """Tier 1 Native Win32 Window Controller."""

    @staticmethod
    def get_window_text(hwnd: int) -> str:
        """Get window title text."""
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value

    @staticmethod
    def get_window_pid(hwnd: int) -> int:
        """Get process ID owning the window."""
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    @staticmethod
    def is_window_visible(hwnd: int) -> bool:
        """Check if window is truly visible and not a cloaked/tool window."""
        if not user32.IsWindowVisible(hwnd):
            return False
        # Skip 0-dimension windows
        rect = RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            if (rect.right - rect.left) <= 0 or (rect.bottom - rect.top) <= 0:
                return False
        return True

    def list_windows(self, query: Optional[str] = None) -> Dict[str, Any]:
        """List all visible top-level windows with title, hwnd, and pid."""
        windows: List[Dict[str, Any]] = []

        def enum_handler(hwnd: wintypes.HWND, lparam: wintypes.LPARAM) -> bool:
            if self.is_window_visible(hwnd):
                title = self.get_window_text(hwnd).strip()
                if title:
                    pid = self.get_window_pid(hwnd)
                    if not query or query.lower() in title.lower():
                        windows.append({
                            "hwnd": int(hwnd),
                            "title": title,
                            "pid": pid,
                        })
            return True

        cb = WNDENUMPROC(enum_handler)
        try:
            user32.EnumWindows(cb, 0)
        except Exception:
            pass

        # If empty (e.g. running from background session or service), query winsta0\default
        if not windows:
            try:
                hwinsta = user32.OpenWindowStationW("winsta0", False, 0x037F)
                if hwinsta:
                    hdesk = user32.OpenDesktopW("default", 0, False, 0x01FF)
                    if hdesk:
                        user32.EnumDesktopWindows(hdesk, cb, 0)
            except Exception:
                pass

        return {
            "success": True,
            "count": len(windows),
            "windows": windows,
        }

    def get_active_window(self) -> Dict[str, Any]:
        """Get currently active/foreground window."""
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            # In headless environments, check if any top-level window exists
            win_list = self.list_windows()
            if win_list["windows"]:
                first = win_list["windows"][0]
                return {
                    "success": True,
                    "hwnd": first["hwnd"],
                    "title": first["title"],
                    "pid": first["pid"],
                    "note": "fallback_top_window",
                }
            return {"success": False, "error": "No active foreground window found."}

        title = self.get_window_text(hwnd)
        pid = self.get_window_pid(hwnd)
        return {
            "success": True,
            "hwnd": int(hwnd),
            "title": title,
            "pid": pid,
        }

    def find_window(self, query: str) -> Optional[int]:
        """Find window HWND by title substring (case-insensitive)."""
        clean_q = query.strip().lower()
        matched_hwnd = None

        def enum_handler(hwnd: wintypes.HWND, lparam: wintypes.LPARAM) -> bool:
            nonlocal matched_hwnd
            if self.is_window_visible(hwnd):
                title = self.get_window_text(hwnd).lower()
                if clean_q in title:
                    matched_hwnd = int(hwnd)
                    return False  # Stop enumeration
            return True

        cb = WNDENUMPROC(enum_handler)
        user32.EnumWindows(cb, 0)
        return matched_hwnd

    def window_exists(self, query: str) -> bool:
        """Check if window matching query exists."""
        return self.find_window(query) is not None

    def activate_window(self, title_or_hwnd: Any) -> Dict[str, Any]:
        """Bring window to foreground and focus it."""
        hwnd = title_or_hwnd if isinstance(title_or_hwnd, int) else self.find_window(str(title_or_hwnd))
        if not hwnd:
            return {"success": False, "error": f"Window '{title_or_hwnd}' not found."}

        try:
            # Restore if minimized
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)

            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
            title = self.get_window_text(hwnd)
            return {"success": True, "hwnd": hwnd, "title": title, "message": f"Activated window '{title}'."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def minimize_window(self, title_or_hwnd: Any) -> Dict[str, Any]:
        """Minimize window."""
        hwnd = title_or_hwnd if isinstance(title_or_hwnd, int) else self.find_window(str(title_or_hwnd))
        if not hwnd:
            return {"success": False, "error": f"Window '{title_or_hwnd}' not found."}

        res = user32.ShowWindow(hwnd, SW_MINIMIZE)
        title = self.get_window_text(hwnd)
        return {"success": True, "hwnd": hwnd, "title": title, "message": f"Minimized window '{title}'."}

    def maximize_window(self, title_or_hwnd: Any) -> Dict[str, Any]:
        """Maximize window."""
        hwnd = title_or_hwnd if isinstance(title_or_hwnd, int) else self.find_window(str(title_or_hwnd))
        if not hwnd:
            return {"success": False, "error": f"Window '{title_or_hwnd}' not found."}

        res = user32.ShowWindow(hwnd, SW_MAXIMIZE)
        title = self.get_window_text(hwnd)
        return {"success": True, "hwnd": hwnd, "title": title, "message": f"Maximized window '{title}'."}

    def restore_window(self, title_or_hwnd: Any) -> Dict[str, Any]:
        """Restore window from minimized/maximized state."""
        hwnd = title_or_hwnd if isinstance(title_or_hwnd, int) else self.find_window(str(title_or_hwnd))
        if not hwnd:
            return {"success": False, "error": f"Window '{title_or_hwnd}' not found."}

        res = user32.ShowWindow(hwnd, SW_RESTORE)
        title = self.get_window_text(hwnd)
        return {"success": True, "hwnd": hwnd, "title": title, "message": f"Restored window '{title}'."}

    def snap_window(self, title_or_hwnd: Any, position: str = "left") -> Dict[str, Any]:
        """
        Snap window to screen boundaries: 'left', 'right', 'top', 'bottom', or 'full'.
        Uses Win32 work area metrics.
        """
        hwnd = title_or_hwnd if isinstance(title_or_hwnd, int) else self.find_window(str(title_or_hwnd))
        if not hwnd:
            return {"success": False, "error": f"Window '{title_or_hwnd}' not found."}

        # Restore window before moving/resizing
        user32.ShowWindow(hwnd, SW_RESTORE)

        # Get desktop work area (excludes taskbar)
        work_area = RECT()
        SPI_GETWORKAREA = 0x0030
        user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(work_area), 0)

        wa_w = work_area.right - work_area.left
        wa_h = work_area.bottom - work_area.top
        wa_x = work_area.left
        wa_y = work_area.top

        pos = position.strip().lower()
        if pos == "left":
            x, y, w, h = wa_x, wa_y, wa_w // 2, wa_h
        elif pos == "right":
            x, y, w, h = wa_x + (wa_w // 2), wa_y, wa_w // 2, wa_h
        elif pos == "top":
            x, y, w, h = wa_x, wa_y, wa_w, wa_h // 2
        elif pos == "bottom":
            x, y, w, h = wa_x, wa_y + (wa_h // 2), wa_w, wa_h // 2
        elif pos in ("full", "maximize"):
            x, y, w, h = wa_x, wa_y, wa_w, wa_h
        else:
            return {"success": False, "error": f"Unsupported snap position '{position}'. Use left, right, top, bottom, or full."}

        user32.MoveWindow(hwnd, x, y, w, h, True)
        user32.SetForegroundWindow(hwnd)

        title = self.get_window_text(hwnd)
        return {
            "success": True,
            "hwnd": hwnd,
            "title": title,
            "position": pos,
            "bounds": {"x": x, "y": y, "width": w, "height": h},
            "message": f"Snapped window '{title}' to {pos}.",
        }


# Singleton instance
native_windows = NativeWindowManager()
