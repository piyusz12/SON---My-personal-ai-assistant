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
    """Open a Windows application by name."""
    key = name.strip().lower()

    # Check known apps first
    cmd = APP_REGISTRY.get(key)
    if cmd:
        try:
            subprocess.Popen(cmd, shell=True)
            return f"Opened {name}."
        except Exception as e:
            return f"Failed to open {name}: {e}"

    # Try as a direct command
    try:
        subprocess.Popen(f"start {name}", shell=True)
        return f"Attempted to open {name}."
    except Exception as e:
        return f"Could not open '{name}': {e}"


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
#  Terminal Commands (Whitelisted)
# ═══════════════════════════════════════════════════════════

def run_terminal_command(command: str) -> str:
    """Run a whitelisted terminal command and return output."""
    # Safety check against whitelist
    cmd_lower = command.strip().lower()
    allowed = False
    for safe_cmd in config.TERMINAL_COMMAND_WHITELIST:
        if cmd_lower.startswith(safe_cmd.lower()):
            allowed = True
            break

    if not allowed:
        return (
            f"Command '{command}' is not in the allowed whitelist. "
            f"Allowed commands: {', '.join(config.TERMINAL_COMMAND_WHITELIST)}"
        )

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
        output = result.stdout or ""
        err = result.stderr or ""

        if result.returncode != 0 and err:
            return f"Command exited with code {result.returncode}:\n{err}\n{output}"
        return output if output else "Command completed (no output)."
    except subprocess.TimeoutExpired:
        return f"Command timed out after 30 seconds."
    except Exception as e:
        return f"Failed to run command: {e}"


# ═══════════════════════════════════════════════════════════
#  Registration — Register all tools with the ToolRegistry
# ═══════════════════════════════════════════════════════════

def register_all(registry):
    """Register all Windows control tools with a ToolRegistry."""

    registry.register(
        name="open_application",
        func=open_application,
        description="Open a Windows application by name (e.g. 'VS Code', 'Chrome', 'Spotify', 'Steam', 'Docker Desktop')",
        params={"name": {"type": "string", "description": "Application name to open"}},
        required=["name"],
        category="system",
    )

    registry.register(
        name="close_application",
        func=close_application,
        description="Close a running application by name",
        params={"name": {"type": "string", "description": "Application name to close"}},
        required=["name"],
        category="system",
    )

    registry.register(
        name="set_volume",
        func=set_volume,
        description="Set the system volume level (0 to 100)",
        params={"level": {"type": "integer", "description": "Volume level from 0 (mute) to 100 (max)"}},
        required=["level"],
        category="system",
    )

    registry.register(
        name="get_volume",
        func=get_volume,
        description="Get the current system volume level",
        params={},
        category="system",
    )

    registry.register(
        name="set_brightness",
        func=set_brightness,
        description="Set screen brightness level (0 to 100)",
        params={"level": {"type": "integer", "description": "Brightness level from 0 to 100"}},
        required=["level"],
        category="system",
    )

    registry.register(
        name="get_brightness",
        func=get_brightness,
        description="Get the current screen brightness level",
        params={},
        category="system",
    )

    registry.register(
        name="shutdown_pc",
        func=shutdown_pc,
        description="Schedule a system shutdown (default 30 second delay to allow cancellation)",
        params={"delay_seconds": {"type": "integer", "description": "Delay in seconds before shutdown", "default": 30}},
        category="system",
        confirm=True,
    )

    registry.register(
        name="restart_pc",
        func=restart_pc,
        description="Schedule a system restart (default 30 second delay)",
        params={"delay_seconds": {"type": "integer", "description": "Delay in seconds before restart", "default": 30}},
        category="system",
        confirm=True,
    )

    registry.register(
        name="cancel_shutdown",
        func=cancel_shutdown,
        description="Cancel a pending shutdown or restart",
        params={},
        category="system",
    )

    registry.register(
        name="lock_pc",
        func=lock_pc,
        description="Lock the workstation",
        params={},
        category="system",
    )

    registry.register(
        name="sleep_pc",
        func=sleep_pc,
        description="Put the PC to sleep",
        params={},
        category="system",
        confirm=True,
    )

    registry.register(
        name="list_processes",
        func=list_processes,
        description="List running processes sorted by CPU or memory usage",
        params={
            "sort_by": {"type": "string", "description": "Sort by 'cpu' or 'memory'", "enum": ["cpu", "memory"], "default": "memory"},
            "limit": {"type": "integer", "description": "Number of processes to show", "default": 15},
        },
        category="system",
    )

    registry.register(
        name="kill_process",
        func=kill_process,
        description="Kill a process by name or PID",
        params={"name_or_pid": {"type": "string", "description": "Process name or PID to kill"}},
        required=["name_or_pid"],
        category="system",
        confirm=True,
    )

    registry.register(
        name="get_system_info",
        func=get_system_info,
        description="Get system resource usage: CPU, RAM, GPU, disk, battery",
        params={},
        category="system",
    )

    registry.register(
        name="open_folder",
        func=open_folder,
        description="Open a folder in File Explorer",
        params={"path": {"type": "string", "description": "Full path to the folder to open"}},
        required=["path"],
        category="system",
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
        category="system",
    )

    registry.register(
        name="run_terminal_command",
        func=run_terminal_command,
        description="Run a safe, whitelisted terminal command and return output (e.g. 'git status', 'pip list', 'systeminfo')",
        params={"command": {"type": "string", "description": "The terminal command to run"}},
        required=["command"],
        category="system",
    )
