# tools/windows_control.py — Windows PC Control Tools for SON
"""
System control tools that SON can invoke via function calling.
Covers: app launching, volume, brightness, processes, system info, file search, etc.
"""
import os
import subprocess
import ctypes
import json
import logging
from pathlib import Path

import config
from core.config import Config
logger = Config.get_logger(__name__)


# ═══════════════════════════════════════════════════════════
#  Application Management
# ═══════════════════════════════════════════════════════════

# Known application paths / commands on Windows
APP_REGISTRY = {
    "vscode":       r"code",
    "vs code":      r"code",
    "visual studio code": r"code",
    "chrome":       r"start chrome",
    "google chrome": r"start chrome",
    "firefox":      r"start firefox",
    "edge":         r"start msedge",
    "notepad":      r"notepad",
    "explorer":     r"explorer",
    "file explorer": r"explorer",
    "calculator":   r"calc",
    "terminal":     r"wt",
    "windows terminal": r"wt",
    "cmd":          r"cmd",
    "powershell":   r"powershell",
    "spotify":      r"start spotify:",
    "steam":        r"start steam://open/main",
    "discord":      r"start discord:",
    "task manager": r"taskmgr",
    "settings":     r"start ms-settings:",
    "paint":        r"mspaint",
    "snipping tool": r"snippingtool",
    "obs":          r"start obs64",
    "docker":       r"start docker",
    "docker desktop": r'start "" "C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"',
}


def open_application(name: str) -> str:
    """Open a Windows application, file, or project by name or path."""
    import re
    raw_name = name.strip()
    key = raw_name.lower()

    # 1. Check known apps in registry
    cmd = APP_REGISTRY.get(key)
    if cmd:
        try:
            subprocess.Popen(cmd, shell=True)
            return f"Opened {raw_name}."
        except Exception as e:
            return f"Failed to open {raw_name}: {e}"

    # 2. Check if name is a direct path to a file or folder
    direct_path = Path(raw_name)
    if direct_path.exists():
        try:
            os.startfile(str(direct_path.resolve()))
            return f"Opened '{direct_path.name}'."
        except Exception as e:
            return f"Failed to open path '{raw_name}': {e}"

    # 3. Clean conversational phrases ("that calculator you made", "the app", "calculator app")
    clean_target = re.sub(r"\b(that|the|my|you|made|created|built|app|application|please|open)\b", "", key, flags=re.IGNORECASE).strip()

    # 4. Search local workspace (e.g. C:\AI and C:\AI\SON) for matching folders or files
    search_dirs = [
        Config.ROOT_DIR,
        Config.ROOT_DIR.parent,
    ]
    candidate_folders = []
    for base in search_dirs:
        if not base.exists():
            continue
        for child in base.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                child_name_lower = child.name.lower().replace("_", " ").replace("-", " ")
                if clean_target and (clean_target in child_name_lower or child_name_lower in clean_target):
                    index_html = child / "index.html"
                    if index_html.exists():
                        os.startfile(str(index_html))
                        return f"Opened {child.name} ({index_html.name})."
                    os.startfile(str(child))
                    return f"Opened {child.name}."
                if child.name not in ("SON", "node_modules", "logs", "__pycache__", "build", ".venv", "native", "config", "memory", "core", "hud", "vision", "gui", "benchmarks", "plugins", "agents", "ipc", "tools"):
                    if (child / "index.html").exists() or (child / "main.py").exists() or (child / "app.py").exists():
                        candidate_folders.append(child)

    # If user said "that app" / "the app" without specific name, open the most recent project folder
    if not clean_target and candidate_folders:
        latest = max(candidate_folders, key=lambda f: f.stat().st_mtime, default=None)
        if latest:
            index_html = latest / "index.html"
            if index_html.exists():
                os.startfile(str(index_html))
                return f"Opened latest project {latest.name} ({index_html.name})."
            os.startfile(str(latest))
            return f"Opened latest project {latest.name}."

    # 5. Try safe Windows start command
    try:
        subprocess.Popen(f'start "" "{raw_name}"', shell=True)
        return f"Attempted to open {raw_name}."
    except Exception as e:
        return f"Could not open '{raw_name}': {e}"


def close_application(name: str) -> str:
    """Close a running application by name."""
    import psutil

    key = name.strip().lower()
    killed = []

    # Map friendly names to process names
    process_map = {
        "chrome": "chrome.exe",
        "google chrome": "chrome.exe",
        "firefox": "firefox.exe",
        "edge": "msedge.exe",
        "vscode": "Code.exe",
        "vs code": "Code.exe",
        "spotify": "Spotify.exe",
        "discord": "Discord.exe",
        "steam": "steam.exe",
        "notepad": "notepad.exe",
        "obs": "obs64.exe",
        "docker": "Docker Desktop.exe",
    }

    target = process_map.get(key, f"{key}.exe")

    for proc in psutil.process_iter(["name", "pid"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == target.lower():
                proc.terminate()
                killed.append(proc.info["name"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if killed:
        return f"Closed {len(killed)} instance(s) of {name}."
    return f"No running process found for '{name}'."


# ═══════════════════════════════════════════════════════════
#  Volume Control
# ═══════════════════════════════════════════════════════════

def set_volume(level: int) -> str:
    """Set system volume (0 to 100)."""
    try:
        import comtypes
        comtypes.CoInitialize()
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            from ctypes import cast, POINTER

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None
            )
            volume = cast(interface, POINTER(IAudioEndpointVolume))

            level = max(0, min(100, int(level)))
            if level == 0:
                volume.SetMute(1, None)
                return "Volume muted."
            else:
                volume.SetMute(0, None)
                scalar = level / 100.0
                volume.SetMasterVolumeLevelScalar(scalar, None)
                return f"Volume set to {level}%."
        finally:
            try:
                comtypes.CoUninitialize()
            except Exception:
                pass
    except ImportError:
        try:
            val = int(65535 * int(level) / 100)
            subprocess.run(
                ["nircmd", "setsysvolume", str(val)],
                capture_output=True,
            )
            return f"Volume set to {level}% (via nircmd)."
        except Exception as e:
            logger.warning(f"Fallback nircmd volume set error: {e}")
            return "Could not set volume. Install pycaw: pip install pycaw"


def get_volume() -> str:
    """Get current system volume level."""
    try:
        import comtypes
        comtypes.CoInitialize()
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            from ctypes import cast, POINTER

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None
            )
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            current = volume.GetMasterVolumeLevelScalar()
            muted = volume.GetMute()

            level = int(current * 100)
            status = " (muted)" if muted else ""
            return f"Current volume: {level}%{status}"
        finally:
            try:
                comtypes.CoUninitialize()
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"get_volume error: {e}")
        return "Could not read volume level."


# ═══════════════════════════════════════════════════════════
#  Brightness Control
# ═══════════════════════════════════════════════════════════

def set_brightness(level: int) -> str:
    """Set screen brightness (0 to 100)."""
    try:
        import screen_brightness_control as sbc
        level = max(0, min(100, int(level)))
        sbc.set_brightness(level)
        return f"Brightness set to {level}%."
    except ImportError:
        return "Install screen-brightness-control: pip install screen-brightness-control"
    except Exception as e:
        return f"Could not set brightness: {e}"


def get_brightness() -> str:
    """Get current screen brightness level."""
    try:
        import screen_brightness_control as sbc
        brightness = sbc.get_brightness()
        return f"Current brightness: {brightness}%"
    except Exception as e:
        return f"Could not read brightness: {e}"


# ═══════════════════════════════════════════════════════════
#  System Power
# ═══════════════════════════════════════════════════════════

def shutdown_pc(delay_seconds: int = 30) -> str:
    """Schedule a system shutdown."""
    delay = max(0, int(delay_seconds))
    subprocess.Popen(f"shutdown /s /t {delay}", shell=True)
    return f"Shutdown scheduled in {delay} seconds. Run 'shutdown /a' to cancel."


def restart_pc(delay_seconds: int = 30) -> str:
    """Schedule a system restart."""
    delay = max(0, int(delay_seconds))
    subprocess.Popen(f"shutdown /r /t {delay}", shell=True)
    return f"Restart scheduled in {delay} seconds. Run 'shutdown /a' to cancel."


def cancel_shutdown() -> str:
    """Cancel a pending shutdown or restart."""
    subprocess.Popen("shutdown /a", shell=True)
    return "Shutdown/restart cancelled."


def lock_pc() -> str:
    """Lock the workstation."""
    ctypes.windll.user32.LockWorkStation()
    return "Workstation locked."


def sleep_pc() -> str:
    """Put the PC to sleep."""
    subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
    return "PC going to sleep."


# ═══════════════════════════════════════════════════════════
#  Process Management
# ═══════════════════════════════════════════════════════════

def list_processes(sort_by: str = "memory", limit: int = 15) -> str:
    """List running processes sorted by CPU or memory usage."""
    import psutil

    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            info = p.info
            mem_mb = info["memory_info"].rss / (1024 * 1024) if info["memory_info"] else 0
            procs.append({
                "pid": info["pid"],
                "name": info["name"] or "Unknown",
                "cpu": info["cpu_percent"] or 0,
                "mem_mb": round(mem_mb, 1),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    key = "mem_mb" if sort_by == "memory" else "cpu"
    procs.sort(key=lambda x: x[key], reverse=True)
    procs = procs[:int(limit)]

    lines = [f"{'PID':<8} {'Name':<30} {'CPU%':<8} {'RAM (MB)':<10}"]
    lines.append("-" * 56)
    for p in procs:
        lines.append(f"{p['pid']:<8} {p['name']:<30} {p['cpu']:<8.1f} {p['mem_mb']:<10.1f}")

    return "\n".join(lines)


def kill_process(name_or_pid: str) -> str:
    """Kill a process by name or PID."""
    import psutil

    # Try as PID first
    try:
        pid = int(name_or_pid)
        proc = psutil.Process(pid)
        proc.terminate()
        return f"Killed process {proc.name()} (PID {pid})."
    except (ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
        pass

    # Try by name
    killed = 0
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            if proc.info["name"] and name_or_pid.lower() in proc.info["name"].lower():
                proc.terminate()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if killed:
        return f"Terminated {killed} process(es) matching '{name_or_pid}'."
    return f"No process found matching '{name_or_pid}'."


# ═══════════════════════════════════════════════════════════
#  System Information
# ═══════════════════════════════════════════════════════════

def get_system_info() -> str:
    """Get system resource usage: CPU, RAM, GPU, disk, battery."""
    import psutil

    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_freq = psutil.cpu_freq()
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")

    lines = [
        "System Information:",
        f"  CPU:  {cpu_percent}% ({cpu_freq.current:.0f} MHz)" if cpu_freq else f"  CPU: {cpu_percent}%",
        f"  RAM:  {ram.used / (1024**3):.1f} / {ram.total / (1024**3):.1f} GB ({ram.percent}%)",
        f"  Disk: {disk.used / (1024**3):.1f} / {disk.total / (1024**3):.1f} GB ({disk.percent}%)",
    ]

    # Battery (if laptop)
    battery = psutil.sensors_battery()
    if battery:
        plug = "plugged in" if battery.power_plugged else "on battery"
        lines.append(f"  Battery: {battery.percent}% ({plug})")

    # GPU info via GPUManager
    try:
        from core.gpu_manager import GPUManager
        gpu_metrics = GPUManager().get_metrics()
        lines.append(
            f"  GPU:  {gpu_metrics.get('gpu_name', 'NVIDIA GPU')} — {gpu_metrics.get('gpu_util', 0)}% util, "
            f"{gpu_metrics.get('vram_used_mb', 0):.0f}/{gpu_metrics.get('vram_total_mb', 0):.0f} MB VRAM, {gpu_metrics.get('gpu_temp_c', 0)}°C"
        )
    except Exception as e:
        logger.debug(f"GPU info fetch error: {e}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
#  File Operations
# ═══════════════════════════════════════════════════════════

def open_folder(path: str) -> str:
    """Open a folder in File Explorer."""
    p = Path(path)
    if not p.exists():
        return f"Path not found: {path}"
    os.startfile(str(p))
    return f"Opened {p.name} in Explorer."


def search_files(query: str, directory: str = "C:\\Users") -> str:
    """Search for files matching a pattern in a directory."""
    results = []
    root = Path(directory)

    if not root.exists():
        return f"Directory not found: {directory}"

    try:
        for p in root.rglob(f"*{query}*"):
            if len(results) >= 20:
                break
            try:
                size = p.stat().st_size
                size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.1f} MB"
                results.append(f"  {p} ({size_str})")
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        return f"Permission denied searching {directory}."

    if not results:
        return f"No files matching '{query}' found in {directory}."

    header = f"Found {len(results)} file(s) matching '{query}':\n"
    return header + "\n".join(results)


# ═══════════════════════════════════════════════════════════
#  Terminal Commands (UNRESTRICTED — gated by ActionExecutor)
# ═══════════════════════════════════════════════════════════

def run_command(command: str, timeout: int = 120) -> str:
    """Run any terminal command (PowerShell/CMD) and return output.

    No whitelist — all commands are allowed. Security is enforced
    by ActionExecutor's permission system (SENSITIVE for destructive
    commands, MEDIUM for everything else).
    """
    cmd_raw = command.strip()
    if not cmd_raw:
        return "Empty command."

    try:
        result = subprocess.run(
            cmd_raw,
            shell=True,
            capture_output=True,
            text=True,
            timeout=int(timeout),
            encoding="utf-8",
            errors="replace",
            cwd=str(Path.home()),
        )
        output = result.stdout or ""
        err = result.stderr or ""

        if result.returncode != 0 and err:
            return f"Exit code {result.returncode}:\n{err}\n{output}".strip()
        return output if output else "Command completed (no output)."

    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds."
    except FileNotFoundError:
        return f"Command not found: {cmd_raw.split()[0]}"
    except Exception as e:
        return f"Failed to run command: {e}"


# ═══════════════════════════════════════════════════════════
#  File Operations (Extended — Full PC Access)
# ═══════════════════════════════════════════════════════════

def read_file(path: str, max_lines: int = 200) -> str:
    """Read contents of a text file and return its content."""
    p = Path(path)
    if not p.exists():
        return f"File not found: {path}"
    if not p.is_file():
        return f"Path is not a file: {path}"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        lines = text.split("\n")
        if len(lines) > int(max_lines):
            return "\n".join(lines[:int(max_lines)]) + f"\n... ({len(lines) - int(max_lines)} more lines)"
        return text
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str) -> str:
    """Write or create a text file with the given content."""
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written {len(content)} characters to {p.name}."
    except Exception as e:
        return f"Error writing file: {e}"


def create_directory(path: str) -> str:
    """Create a new directory (and parent directories if needed)."""
    p = Path(path)
    try:
        p.mkdir(parents=True, exist_ok=True)
        return f"Created directory: {p}"
    except Exception as e:
        return f"Error creating directory: {e}"


# ═══════════════════════════════════════════════════════════
#  Clipboard
# ═══════════════════════════════════════════════════════════

def get_clipboard() -> str:
    """Get current clipboard text contents."""
    try:
        result = subprocess.run(
            ["powershell", "-command", "Get-Clipboard"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.stdout else "Clipboard is empty."
    except Exception as e:
        return f"Error reading clipboard: {e}"


def set_clipboard(text: str) -> str:
    """Set clipboard text contents."""
    try:
        subprocess.run(
            ["powershell", "-command", f"Set-Clipboard -Value '{text}'"],
            capture_output=True, text=True, timeout=5,
        )
        return f"Copied to clipboard ({len(text)} chars)."
    except Exception as e:
        return f"Error setting clipboard: {e}"


# ═══════════════════════════════════════════════════════════
#  Screenshots
# ═══════════════════════════════════════════════════════════

def take_screenshot(save_path: str = "") -> str:
    """Take a screenshot and save to file."""
    try:
        from PIL import ImageGrab
        from datetime import datetime

        if not save_path:
            save_dir = Path(__file__).parent.parent / "screenshots"
            save_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = str(save_dir / f"screenshot_{timestamp}.png")

        img = ImageGrab.grab()
        img.save(save_path)
        return f"Screenshot saved to {save_path}"
    except ImportError:
        return "Pillow not installed. Run: pip install Pillow"
    except Exception as e:
        return f"Screenshot failed: {e}"


# ═══════════════════════════════════════════════════════════
#  System Info (Extended)
# ═══════════════════════════════════════════════════════════

def get_wifi_info() -> str:
    """Get current WiFi network information."""
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        if result.stdout:
            lines = []
            for line in result.stdout.split("\n"):
                line = line.strip()
                if any(k in line.lower() for k in ["ssid", "signal", "radio", "state", "band", "channel"]):
                    lines.append(f"  {line}")
            return "\n".join(lines) if lines else "No WiFi info available."
        return "WiFi info unavailable."
    except Exception as e:
        return f"Error getting WiFi info: {e}"


def get_battery_info() -> str:
    """Get battery status and percentage."""
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery:
            plug = "plugged in" if battery.power_plugged else "on battery"
            secs_left = battery.secsleft
            time_left = f", {secs_left // 3600}h {(secs_left % 3600) // 60}m remaining" if secs_left > 0 and not battery.power_plugged else ""
            return f"Battery: {battery.percent}% ({plug}{time_left})"
        return "No battery detected (desktop PC)."
    except Exception as e:
        return f"Error getting battery info: {e}"


def list_installed_apps(query: str = "") -> str:
    """List installed applications, optionally filtered by name."""
    try:
        ps_cmd = 'Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Select-Object DisplayName, DisplayVersion | Format-Table -AutoSize'
        result = subprocess.run(
            ["powershell", "-command", ps_cmd],
            capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace",
        )
        if result.stdout:
            lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip() and l.strip() != "---"]
            if query:
                lines = [l for l in lines if query.lower() in l.lower()]
            return "\n".join(lines[:30]) if lines else f"No apps matching '{query}'."
        return "Could not list installed applications."
    except Exception as e:
        return f"Error listing apps: {e}"


# ═══════════════════════════════════════════════════════════
#  Registration — Register all tools with the ToolRegistry
# ═══════════════════════════════════════════════════════════

def register_all(registry):
    """Register all Windows control tools with a ToolRegistry."""
    from core.config import SecurityLevel

    # ── Application Control ───────────────────────────────────
    registry.register(
        name="open_application",
        func=open_application,
        description="Open a Windows application by name (e.g. 'VS Code', 'Chrome', 'Spotify', 'Steam', 'Docker Desktop')",
        params={"name": {"type": "string", "description": "Application name to open"}},
        required=["name"],
        category="system",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="close_application",
        func=close_application,
        description="Close a running application by name",
        params={"name": {"type": "string", "description": "Application name to close"}},
        required=["name"],
        category="system",
        security_level=SecurityLevel.MEDIUM,
    )

    # ── Volume / Brightness ───────────────────────────────────
    registry.register(
        name="set_volume",
        func=set_volume,
        description="Set the system volume level (0 to 100)",
        params={"level": {"type": "integer", "description": "Volume level from 0 (mute) to 100 (max)"}},
        required=["level"],
        category="system",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="get_volume",
        func=get_volume,
        description="Get the current system volume level",
        params={},
        category="system",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="set_brightness",
        func=set_brightness,
        description="Set screen brightness level (0 to 100)",
        params={"level": {"type": "integer", "description": "Brightness level from 0 to 100"}},
        required=["level"],
        category="system",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="get_brightness",
        func=get_brightness,
        description="Get the current screen brightness level",
        params={},
        category="system",
        security_level=SecurityLevel.SAFE,
    )

    # ── System Power (CRITICAL — always confirm) ──────────────
    registry.register(
        name="shutdown_pc",
        func=shutdown_pc,
        description="Schedule a system shutdown (default 30 second delay to allow cancellation)",
        params={"delay_seconds": {"type": "integer", "description": "Delay in seconds before shutdown", "default": 30}},
        category="system",
        confirm=True,
        security_level=SecurityLevel.CRITICAL,
    )

    registry.register(
        name="restart_pc",
        func=restart_pc,
        description="Schedule a system restart (default 30 second delay)",
        params={"delay_seconds": {"type": "integer", "description": "Delay in seconds before restart", "default": 30}},
        category="system",
        confirm=True,
        security_level=SecurityLevel.CRITICAL,
    )

    registry.register(
        name="cancel_shutdown",
        func=cancel_shutdown,
        description="Cancel a pending shutdown or restart",
        params={},
        category="system",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="lock_pc",
        func=lock_pc,
        description="Lock the workstation",
        params={},
        category="system",
        security_level=SecurityLevel.MEDIUM,
    )

    registry.register(
        name="sleep_pc",
        func=sleep_pc,
        description="Put the PC to sleep",
        params={},
        category="system",
        confirm=True,
        security_level=SecurityLevel.SENSITIVE,
    )

    # ── Process Management ────────────────────────────────────
    registry.register(
        name="list_processes",
        func=list_processes,
        description="List running processes sorted by CPU or memory usage",
        params={
            "sort_by": {"type": "string", "description": "Sort by 'cpu' or 'memory'", "enum": ["cpu", "memory"], "default": "memory"},
            "limit": {"type": "integer", "description": "Number of processes to show", "default": 15},
        },
        category="system",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="kill_process",
        func=kill_process,
        description="Kill a process by name or PID",
        params={"name_or_pid": {"type": "string", "description": "Process name or PID to kill"}},
        required=["name_or_pid"],
        category="system",
        confirm=True,
        security_level=SecurityLevel.SENSITIVE,
    )

    # ── System Information ────────────────────────────────────
    registry.register(
        name="get_system_info",
        func=get_system_info,
        description="Get system resource usage: CPU, RAM, GPU, disk, battery",
        params={},
        category="system",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="get_wifi_info",
        func=get_wifi_info,
        description="Get current WiFi network info (SSID, signal strength, band)",
        params={},
        category="system",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="get_battery_info",
        func=get_battery_info,
        description="Get battery status, percentage, and time remaining",
        params={},
        category="system",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="list_installed_apps",
        func=list_installed_apps,
        description="List installed applications on the PC, optionally filtered by name",
        params={"query": {"type": "string", "description": "Optional filter by app name", "default": ""}},
        category="system",
        security_level=SecurityLevel.SAFE,
    )

    # ── File Operations ───────────────────────────────────────
    registry.register(
        name="open_folder",
        func=open_folder,
        description="Open a folder in File Explorer",
        params={"path": {"type": "string", "description": "Full path to the folder to open"}},
        required=["path"],
        category="files",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="search_files",
        func=search_files,
        description="Search for files by name pattern in a directory",
        params={
            "query": {"type": "string", "description": "Search query (partial filename)"},
            "directory": {"type": "string", "description": "Directory to search in", "default": "C:\\Users"},
        },
        required=["query"],
        category="files",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="read_file",
        func=read_file,
        description="Read contents of a text file",
        params={
            "path": {"type": "string", "description": "Full path to the file to read"},
            "max_lines": {"type": "integer", "description": "Max lines to read", "default": 200},
        },
        required=["path"],
        category="files",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="write_file",
        func=write_file,
        description="Write or create a text file with given content",
        params={
            "path": {"type": "string", "description": "Full path for the file"},
            "content": {"type": "string", "description": "Text content to write"},
        },
        required=["path", "content"],
        category="files",
        security_level=SecurityLevel.MEDIUM,
    )

    registry.register(
        name="create_directory",
        func=create_directory,
        description="Create a new directory (and parent directories if needed)",
        params={"path": {"type": "string", "description": "Full path of directory to create"}},
        required=["path"],
        category="files",
        security_level=SecurityLevel.SAFE,
    )

    # ── Clipboard ─────────────────────────────────────────────
    registry.register(
        name="get_clipboard",
        func=get_clipboard,
        description="Get current clipboard text contents",
        params={},
        category="system",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="set_clipboard",
        func=set_clipboard,
        description="Set clipboard text contents",
        params={"text": {"type": "string", "description": "Text to copy to clipboard"}},
        required=["text"],
        category="system",
        security_level=SecurityLevel.SAFE,
    )

    # ── Screenshots ───────────────────────────────────────────
    registry.register(
        name="take_screenshot",
        func=take_screenshot,
        description="Take a screenshot and save to file",
        params={"save_path": {"type": "string", "description": "Optional save path (auto-generated if empty)", "default": ""}},
        category="system",
        security_level=SecurityLevel.SAFE,
    )

    # ── Terminal Commands (UNRESTRICTED) ──────────────────────
    registry.register(
        name="run_command",
        func=run_command,
        description="Run ANY terminal command (PowerShell/CMD/Python/npm/git etc.) and return output. Use this for installing packages, running scripts, system administration, and any command-line task.",
        params={
            "command": {"type": "string", "description": "The terminal command to run"},
            "timeout": {"type": "integer", "description": "Max seconds to wait", "default": 120},
        },
        required=["command"],
        category="system",
        security_level=SecurityLevel.MEDIUM,  # Dynamically escalated to SENSITIVE by ActionExecutor for destructive commands
    )

