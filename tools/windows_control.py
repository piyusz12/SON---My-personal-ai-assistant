# tools/windows_control.py — Windows PC Control Tools for SON
"""
System control tools that SON can invoke via function calling.
Covers: app launching, volume, brightness, processes, system info, file search, etc.
"""
import os
import shutil
import subprocess
import ctypes
import glob
import json
import logging
import re
from pathlib import Path

import config
from core.config import Config
from core.security.sanitizer import wrap_untrusted_content
logger = Config.get_logger(__name__)


# ═══════════════════════════════════════════════════════════
#  Application Management
# ═══════════════════════════════════════════════════════════

# Known application paths / commands on Windows
OFFICE_WORD_FALLBACKS = [
    r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE",
    r"C:\Program Files\Microsoft Office\Office16\WINWORD.EXE",
    r"C:\Program Files (x86)\Microsoft Office\Office16\WINWORD.EXE",
    r"C:\Program Files\Microsoft Office\Office15\WINWORD.EXE",
]

OFFICE_EXCEL_FALLBACKS = [
    r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
    r"C:\Program Files (x86)\Microsoft Office\root\Office16\EXCEL.EXE",
    r"C:\Program Files\Microsoft Office\Office16\EXCEL.EXE",
    r"C:\Program Files (x86)\Microsoft Office\Office16\EXCEL.EXE",
    r"C:\Program Files\Microsoft Office\Office15\EXCEL.EXE",
]

OFFICE_POWERPNT_FALLBACKS = [
    r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",
    r"C:\Program Files (x86)\Microsoft Office\root\Office16\POWERPNT.EXE",
    r"C:\Program Files\Microsoft Office\Office16\POWERPNT.EXE",
    r"C:\Program Files (x86)\Microsoft Office\Office16\POWERPNT.EXE",
    r"C:\Program Files\Microsoft Office\Office15\POWERPNT.EXE",
]

OFFICE_OUTLOOK_FALLBACKS = [
    r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE",
    r"C:\Program Files (x86)\Microsoft Office\root\Office16\OUTLOOK.EXE",
    r"C:\Program Files\Microsoft Office\Office16\OUTLOOK.EXE",
    r"C:\Program Files (x86)\Microsoft Office\Office16\OUTLOOK.EXE",
]

OFFICE_ONENOTE_FALLBACKS = [
    r"C:\Program Files\Microsoft Office\root\Office16\ONENOTE.EXE",
    r"C:\Program Files (x86)\Microsoft Office\root\Office16\ONENOTE.EXE",
    r"C:\Program Files\Microsoft Office\Office16\ONENOTE.EXE",
]

APP_REGISTRY = {
    "vscode":               {"type": "exec", "target": "code"},
    "vs code":              {"type": "exec", "target": "code"},
    "visual studio code":   {"type": "exec", "target": "code"},
    "chrome":               {"type": "exec", "target": "chrome"},
    "google chrome":        {"type": "exec", "target": "chrome"},
    "firefox":              {"type": "exec", "target": "firefox"},
    "edge":                 {"type": "exec", "target": "msedge"},
    "notepad":              {"type": "exec", "target": "notepad"},
    "explorer":             {"type": "exec", "target": "explorer"},
    "file explorer":        {"type": "exec", "target": "explorer"},
    "calculator":           {"type": "exec", "target": "calc"},
    "calc":                 {"type": "exec", "target": "calc"},
    "terminal":             {"type": "exec", "target": "wt"},
    "windows terminal":     {"type": "exec", "target": "wt"},
    "cmd":                  {"type": "exec", "target": "cmd"},
    "powershell":           {"type": "exec", "target": "powershell"},
    "spotify":              {"type": "uri",  "target": "spotify:"},
    "steam":                {"type": "uri",  "target": "steam://open/main"},
    "discord":              {"type": "exec", "target": r"C:\Users\%USERNAME%\AppData\Local\Discord\app-*\Discord.exe"},
    "task manager":         {"type": "exec", "target": "taskmgr"},
    "settings":             {"type": "uri",  "target": "ms-settings:"},
    "paint":                {"type": "exec", "target": "mspaint"},
    "snipping tool":        {"type": "exec", "target": "snippingtool"},
    "obs":                  {"type": "exec", "target": "obs64"},
    "docker":               {"type": "exec", "target": "docker"},
    "docker desktop":       {"type": "exec", "target": r"C:\Program Files\Docker\Docker\Docker Desktop.exe"},
    # Microsoft Office Suite
    "word":                 {"type": "exec", "target": "winword", "fallbacks": OFFICE_WORD_FALLBACKS},
    "microsoft word":       {"type": "exec", "target": "winword", "fallbacks": OFFICE_WORD_FALLBACKS},
    "ms word":              {"type": "exec", "target": "winword", "fallbacks": OFFICE_WORD_FALLBACKS},
    "winword":              {"type": "exec", "target": "winword", "fallbacks": OFFICE_WORD_FALLBACKS},
    "office":               {"type": "exec", "target": "winword", "fallbacks": OFFICE_WORD_FALLBACKS},
    "microsoft office":     {"type": "exec", "target": "winword", "fallbacks": OFFICE_WORD_FALLBACKS},
    "microsoft office (word)": {"type": "exec", "target": "winword", "fallbacks": OFFICE_WORD_FALLBACKS},
    "microsoft office word": {"type": "exec", "target": "winword", "fallbacks": OFFICE_WORD_FALLBACKS},
    "office (word)":        {"type": "exec", "target": "winword", "fallbacks": OFFICE_WORD_FALLBACKS},
    "office word":          {"type": "exec", "target": "winword", "fallbacks": OFFICE_WORD_FALLBACKS},
    "word document":        {"type": "exec", "target": "winword", "fallbacks": OFFICE_WORD_FALLBACKS},
    "ms office":            {"type": "exec", "target": "winword", "fallbacks": OFFICE_WORD_FALLBACKS},
    "office 365":           {"type": "exec", "target": "winword", "fallbacks": OFFICE_WORD_FALLBACKS},
    "excel":                {"type": "exec", "target": "excel", "fallbacks": OFFICE_EXCEL_FALLBACKS},
    "microsoft excel":      {"type": "exec", "target": "excel", "fallbacks": OFFICE_EXCEL_FALLBACKS},
    "ms excel":             {"type": "exec", "target": "excel", "fallbacks": OFFICE_EXCEL_FALLBACKS},
    "powerpoint":           {"type": "exec", "target": "powerpnt", "fallbacks": OFFICE_POWERPNT_FALLBACKS},
    "microsoft powerpoint": {"type": "exec", "target": "powerpnt", "fallbacks": OFFICE_POWERPNT_FALLBACKS},
    "ms powerpoint":        {"type": "exec", "target": "powerpnt", "fallbacks": OFFICE_POWERPNT_FALLBACKS},
    "ppt":                  {"type": "exec", "target": "powerpnt", "fallbacks": OFFICE_POWERPNT_FALLBACKS},
    "outlook":              {"type": "exec", "target": "outlook", "fallbacks": OFFICE_OUTLOOK_FALLBACKS},
    "microsoft outlook":    {"type": "exec", "target": "outlook", "fallbacks": OFFICE_OUTLOOK_FALLBACKS},
    "ms outlook":           {"type": "exec", "target": "outlook", "fallbacks": OFFICE_OUTLOOK_FALLBACKS},
    "onenote":              {"type": "exec", "target": "onenote", "fallbacks": OFFICE_ONENOTE_FALLBACKS},
    "microsoft onenote":    {"type": "exec", "target": "onenote", "fallbacks": OFFICE_ONENOTE_FALLBACKS},
}


def open_application(name: str) -> str:
    """Open a Windows application, file, or project by name or path without shell execution."""
    import re
    raw_name = name.strip()
    key = raw_name.lower()

    # Reject command chaining, piping, shell injection, or redirection syntax
    injection_tokens = ["&", ";", "|", "`", "$", ">", "<", "\n", "\r", '"', "'"]
    if any(token in raw_name for token in injection_tokens):
        return f"Security Error: Application name '{name}' contains disallowed characters."

    # 1. Check known apps in registry
    app_entry = APP_REGISTRY.get(key)
    if app_entry:
        try:
            if app_entry["type"] == "uri":
                os.startfile(app_entry["target"])
                return f"Opened {raw_name}."
            else:
                target = app_entry["target"]
                if "%USERNAME%" in target:
                    target = target.replace("%USERNAME%", Path.home().name)
                if "*" in target or "?" in target:
                    matches = sorted(glob.glob(target))
                    if matches:
                        target = matches[-1]
                    else:
                        return f"Application '{name}' not found at expected path."
                resolved = shutil.which(target)
                if not resolved:
                    for fb in app_entry.get("fallbacks", []):
                        if os.path.exists(fb):
                            resolved = fb
                            break
                if not resolved:
                    resolved = target
                subprocess.Popen([resolved], shell=False)
                return f"Opened '{name}'." if key == "discord" else f"Opened {raw_name}."
        except Exception as e:
            return f"Failed to open {raw_name}: {e}"

    # 2. Check if name is a direct path to an existing file or folder
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

    # 5. Resolve system executable safely without shell=True
    resolved_exe = shutil.which(raw_name) or shutil.which(f"{raw_name}.exe")
    if resolved_exe:
        try:
            subprocess.Popen([resolved_exe], shell=False)
            return f"Opened {raw_name}."
        except Exception as e:
            return f"Could not open '{raw_name}': {e}"

    return f"Application '{name}' not found in approved registry or workspace."


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
            if hasattr(devices, "EndpointVolume"):
                volume = devices.EndpointVolume
            elif hasattr(devices, "Activate"):
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = cast(interface, POINTER(IAudioEndpointVolume))
            else:
                interface = devices._dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
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
            if hasattr(devices, "EndpointVolume"):
                volume = devices.EndpointVolume
            elif hasattr(devices, "Activate"):
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = cast(interface, POINTER(IAudioEndpointVolume))
            else:
                interface = devices._dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
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
    subprocess.Popen(["shutdown.exe", "/s", "/t", str(delay)], shell=False)
    return f"Shutdown scheduled in {delay} seconds. Run 'shutdown /a' to cancel."


def restart_pc(delay_seconds: int = 30) -> str:
    """Schedule a system restart."""
    delay = max(0, int(delay_seconds))
    subprocess.Popen(["shutdown.exe", "/r", "/t", str(delay)], shell=False)
    return f"Restart scheduled in {delay} seconds. Run 'shutdown /a' to cancel."


def cancel_shutdown() -> str:
    """Cancel a pending shutdown or restart."""
    subprocess.Popen(["shutdown.exe", "/a"], shell=False)
    return "Shutdown/restart cancelled."


def lock_pc() -> str:
    """Lock the workstation."""
    ctypes.windll.user32.LockWorkStation()
    return "Workstation locked."


def sleep_pc() -> str:
    """Put the PC to sleep."""
    subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], shell=False)
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
    """Get system resource usage: CPU, RAM, GPU, disk, battery (non-blocking)."""
    import psutil

    cpu_percent = psutil.cpu_percent(interval=None)
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
#  Terminal Commands (Isolated E2B MicroVM Execution Only)
# ═══════════════════════════════════════════════════════════

def run_command(command: str, timeout: int = 120) -> str:
    """Execute command safely inside an isolated E2B microVM sandbox.
    Direct arbitrary host execution is permanently disabled by security policy.
    """
    cmd_raw = command.strip()
    if not cmd_raw:
        return "Empty command."

    from services.sandbox.e2b_service import sandbox_service
    res = sandbox_service.execute_terminal_command(command=cmd_raw, timeout=int(timeout))
    if res.success:
        return res.stdout if res.stdout else "Command completed in sandbox (no output)."
    return f"Sandbox Execution Error (Exit {res.exit_code}):\n{res.stderr or res.error_message}"


def run_terminal_command(command: str, timeout: int = 120) -> str:
    """Execute command safely inside isolated E2B microVM sandbox with command injection checks."""
    cmd_raw = command.strip()
    # Reject command chaining, piping, redirection, or destructive injection syntax
    injection_tokens = ["&", ";", "|", "`", "$env:", ">", "<", "&&", "||"]
    if any(token in cmd_raw for token in injection_tokens):
        return f"Security Error: Command '{command}' rejected due to blocked chaining/injection syntax."
    return run_command(command, timeout=timeout)



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
            raw_content = "\n".join(lines[:int(max_lines)]) + f"\n... ({len(lines) - int(max_lines)} more lines)"
        else:
            raw_content = text
        return wrap_untrusted_content(raw_content, source=f"file:{path}", source_type="local_file")
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


def _parse_presentation_slides(content: str, default_title: str = "Presentation") -> list[tuple[str, list[str]]]:
    """Parse presentation text into a list of (slide_title, [bullets])."""
    if not content or not content.strip():
        return [(default_title.replace("_", " ").title(), ["Overview and strategic insights"])]

    # Split on Slide \d+: or double newlines
    raw_blocks = re.split(r"(?:^|\n\n)(?:Slide\s*\d+\s*[:\-]\s*)", content.strip(), flags=re.IGNORECASE)
    blocks = [b.strip() for b in raw_blocks if b.strip()]
    if not blocks:
        blocks = [b.strip() for b in content.split("\n\n") if b.strip()]

    slides = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        # Strip prefixes like "Slide 1:", "1.", "#"
        first_line = re.sub(r"^(?:Slide\s*\d+\s*[:\-]\s*|\d+\.\s*|#+\s*)", "", lines[0], flags=re.IGNORECASE).strip()
        slide_title = first_line if first_line else default_title
        bullets = [re.sub(r"^[-*•]\s*", "", l).strip() for l in lines[1:] if l.strip()]
        slides.append((slide_title, bullets))

    if not slides:
        slides = [(default_title.replace("_", " ").title(), [content.strip()])]

    return slides


def _enrich_slide_bullets(title: str, bullets: list[str]) -> list[str]:
    """If a slide lacks bullet points, generate relevant points based on title."""
    if bullets:
        return bullets

    t_lower = title.lower()
    if "water" in t_lower and ("waste" in t_lower or "westage" in t_lower or "loss" in t_lower):
        return [
            "Billions of liters of potable water lost daily due to pipeline leaks and runoff",
            "Agricultural runoff and industrial overuse exacerbate local shortages",
            "Need for urgent municipal and domestic conservation strategies",
        ]
    elif "water" in t_lower and "management" in t_lower:
        return [
            "Ensures sustainable allocation across agriculture, industry, and households",
            "Protects freshwater reserves and preserves critical river basins",
            "Mitigates climate change impacts and recurring drought cycles",
        ]
    elif "water" in t_lower and "conservation" in t_lower:
        return [
            "Implementation of rainwater harvesting and groundwater recharging",
            "Adoption of micro-irrigation and precision agriculture techniques",
            "Installation of low-flow fixtures and automated leak detectors",
        ]
    elif "recycl" in t_lower or "technolog" in t_lower:
        return [
            "Greywater treatment systems for urban landscaping and cooling",
            "Advanced membrane filtration, reverse osmosis, and ultraviolet purification",
            "Industrial zero liquid discharge (ZLD) closed-loop water recovery",
        ]
    elif "sustainable" in t_lower or "solution" in t_lower or "conclusion" in t_lower or "plan" in t_lower:
        return [
            "Community-driven water governance and public awareness campaigns",
            "Integration of smart water meters and IoT-based grid monitoring",
            "Long-term policy reforms and incentives for water recycling",
        ]
    else:
        clean_t = title.replace("_", " ").strip()
        return [
            f"Key principles and fundamental drivers of {clean_t}",
            "Strategic implementation approaches and industry best practices",
            "Actionable recommendations, monitoring, and measurable outcomes",
        ]


def create_powerpoint_presentation(filename: str, content: str, title: str = "", open_after: bool = True) -> str:
    """
    Create a formatted Microsoft PowerPoint (.pptx) presentation and optionally open it.
    
    Args:
        filename: Name of the presentation (e.g. 'water_wastage.pptx').
        content: The slides content (e.g. 'Slide 1: ... \\n\\nSlide 2: ...').
        title: Presentation heading / topic.
        open_after: If True, opens the presentation in Microsoft PowerPoint immediately.
        
    Returns:
        Status message with the saved presentation path.
    """
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor

        clean_name = (filename or "presentation.pptx").strip()
        if not clean_name.lower().endswith(".pptx"):
            clean_name = clean_name.rsplit(".", 1)[0] + ".pptx" if "." in clean_name else clean_name + ".pptx"

        docs_dir = Path.home() / "Documents"
        docs_dir.mkdir(parents=True, exist_ok=True)
        file_path = docs_dir / clean_name

        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)  # 16:9 widescreen format

        # Parse slides and content
        slides = _parse_presentation_slides(content, title or Path(clean_name).stem)

        for i, (slide_title, bullets) in enumerate(slides):
            if i == 0:
                # Title Slide
                title_layout = prs.slide_layouts[0]
                slide = prs.slides.add_slide(title_layout)
                title_shape = slide.shapes.title
                title_shape.text = slide_title
                if len(slide.placeholders) > 1:
                    subtitle_shape = slide.placeholders[1]
                    subtitle_shape.text = "\n".join(bullets) if bullets else (title or "A Comprehensive Overview")
            else:
                # Content / Bullet Slide
                bullet_layout = prs.slide_layouts[1]
                slide = prs.slides.add_slide(bullet_layout)
                title_shape = slide.shapes.title
                title_shape.text = slide_title
                if len(slide.placeholders) > 1:
                    body_shape = slide.placeholders[1]
                    tf = body_shape.text_frame
                    tf.word_wrap = True
                    enriched_bullets = _enrich_slide_bullets(slide_title, bullets)
                    for b_idx, bullet in enumerate(enriched_bullets):
                        if b_idx == 0:
                            tf.text = bullet
                        else:
                            p = tf.add_paragraph()
                            p.text = bullet

        try:
            prs.save(str(file_path))
        except PermissionError:
            logger.warning(f"File '{file_path}' is locked by another process (e.g. PowerPoint). Closing POWERPNT to update presentation...")
            try:
                import subprocess
                import time
                subprocess.run(["taskkill", "/F", "/IM", "POWERPNT.EXE"], capture_output=True)
                time.sleep(0.35)
                prs.save(str(file_path))
            except Exception as pe:
                logger.error(f"Failed to overwrite locked presentation after taskkill: {pe}")
                alt_name = f"{Path(clean_name).stem}_updated.pptx"
                file_path = docs_dir / alt_name
                prs.save(str(file_path))
                clean_name = alt_name

        if open_after:
            try:
                os.startfile(str(file_path))
                return f"Created presentation '{clean_name}' at {file_path} and opened in Microsoft PowerPoint."
            except Exception as e:
                logger.warning(f"Could not automatically open created pptx: {e}")
                return f"Created presentation '{clean_name}' at {file_path}."

        return f"Created presentation '{clean_name}' at {file_path}."
    except Exception as e:
        logger.error(f"Failed to create PowerPoint presentation: {e}")
        # Safe fallback: create text presentation file
        try:
            txt_name = (filename.replace(".pptx", "").replace(".ppt", "") if filename else "presentation") + ".txt"
            txt_path = Path.home() / "Documents" / txt_name
            txt_path.write_text(content, encoding="utf-8")
            if open_after:
                os.startfile(str(txt_path))
            return f"Created presentation outline at {txt_path} and opened it."
        except Exception:
            return f"Failed to create presentation: {e}"


def create_presentation(filename: str, content: str = "", title: str = "", open_after: bool = True) -> str:
    """
    Create a formatted Microsoft PowerPoint (.pptx) presentation and optionally open it.
    """
    return create_powerpoint_presentation(filename, content, title, open_after)


def _parse_or_generate_spreadsheet_data(content: str, topic: str = "") -> tuple[list[str], list[list[any]]]:
    """Parse CSV, TSV, or Markdown table content, or generate tailored default data."""
    import csv, io

    if content and content.strip():
        lines = [l.strip() for l in content.strip().splitlines() if l.strip()]

        # Check for Markdown table
        if any("|" in l for l in lines):
            table_rows = []
            for line in lines:
                if re.match(r"^\|?\s*[-:]+[-| :]*$", line):
                    continue
                parts = [p.strip() for p in line.strip("|").split("|")]
                if parts:
                    table_rows.append(parts)
            if len(table_rows) >= 2:
                return table_rows[0], table_rows[1:]

        # Check for CSV / TSV
        if len(lines) >= 2 and ("," in lines[0] or "\t" in lines[0]):
            delim = "\t" if "\t" in lines[0] else ","
            reader = csv.reader(io.StringIO(content.strip()), delimiter=delim)
            csv_rows = [row for row in reader if row]
            if len(csv_rows) >= 2:
                return csv_rows[0], csv_rows[1:]

    # Default datasets based on topic
    t_lower = (topic or "").lower()
    if any(k in t_lower for k in ("student", "grade", "school", "class", "marks", "attendance", "exam")) or not topic or topic == "Spreadsheet":
        headers = ["Student ID", "Full Name", "Grade/Class", "Subject", "Score / Marks", "Attendance %", "Status"]
        rows = [
            ["STU-101", "John Doe", "Grade 10", "Mathematics", 92, "96%", "Passed with Distinction"],
            ["STU-102", "Alice Smith", "Grade 10", "Mathematics", 88, "94%", "Passed"],
            ["STU-103", "Bob Johnson", "Grade 10", "Mathematics", 85, "91%", "Passed"],
            ["STU-104", "Jane Williams", "Grade 10", "Mathematics", 95, "98%", "Passed with Distinction"],
            ["STU-105", "Mike Brown", "Grade 10", "Mathematics", 79, "89%", "Passed"],
        ]
        return headers, rows
    elif any(k in t_lower for k in ("budget", "finance", "expense", "cost", "money")):
        headers = ["Category", "Item Description", "Allocated Budget ($)", "Actual Expense ($)", "Variance ($)", "Status"]
        rows = [
            ["Personnel", "Salaries & Operations", 25000, 24200, 800, "Under Budget"],
            ["Infrastructure", "Cloud Hosting & Servers", 8000, 7850, 150, "Under Budget"],
            ["Software", "Licenses & Subscriptions", 3500, 3600, -100, "Over Budget"],
            ["Marketing", "Outreach & Campaigns", 5000, 4800, 200, "Under Budget"],
            ["Contingency", "Emergency Buffer", 4000, 1200, 2800, "Under Budget"],
        ]
        return headers, rows
    elif any(k in t_lower for k in ("sale", "product", "inventory", "stock")):
        headers = ["SKU / Product ID", "Product Name", "Category", "Unit Price ($)", "Stock Quantity", "Total Value ($)", "Status"]
        rows = [
            ["PRD-001", "Wireless Ergonomic Mouse", "Electronics", 49.99, 120, 5998.80, "In Stock"],
            ["PRD-002", "Mechanical Keyboard", "Electronics", 89.99, 75, 6749.25, "In Stock"],
            ["PRD-003", "27-inch 4K Monitor", "Displays", 329.99, 30, 9899.70, "Low Stock"],
            ["PRD-004", "USB-C Multiport Dock", "Accessories", 59.99, 90, 5399.10, "In Stock"],
            ["PRD-005", "Noise Cancelling Headset", "Audio", 149.99, 45, 6749.55, "In Stock"],
        ]
        return headers, rows
    else:
        clean_topic = topic.replace("_", " ").title()
        headers = ["ID", "Item / Description", "Category", "Quantity", "Value ($)", "Status", "Notes"]
        rows = [
            ["REC-001", f"{clean_topic} Item 1", "General", 10, 100, "Active", "Verified"],
            ["REC-002", f"{clean_topic} Item 2", "General", 25, 250, "Active", "Verified"],
            ["REC-003", f"{clean_topic} Item 3", "General", 15, 150, "Pending", "Reviewing"],
            ["REC-004", f"{clean_topic} Item 4", "General", 40, 400, "Active", "Verified"],
            ["REC-005", f"{clean_topic} Item 5", "General", 5, 50, "Completed", "Archived"],
        ]
        return headers, rows


def create_excel_spreadsheet(filename: str, content: str = "", title: str = "", open_after: bool = True) -> str:
    """
    Create a formatted Microsoft Excel (.xlsx) spreadsheet and optionally open it.
    
    Args:
        filename: Name of the spreadsheet (e.g. 'students.xlsx' or 'budget.xlsx').
        content: Table data in CSV, TSV, or Markdown format, or empty for smart template.
        title: Worksheet title or data topic.
        open_after: If True, opens the spreadsheet in Microsoft Excel immediately.
        
    Returns:
        Status message with the saved spreadsheet path.
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        clean_name = (filename or "spreadsheet.xlsx").strip()
        if not clean_name.lower().endswith(".xlsx"):
            clean_name = clean_name.rsplit(".", 1)[0] + ".xlsx" if "." in clean_name else clean_name + ".xlsx"

        docs_dir = Path.home() / "Documents"
        docs_dir.mkdir(parents=True, exist_ok=True)
        file_path = docs_dir / clean_name

        wb = openpyxl.Workbook()
        ws = wb.active

        sheet_title = (title or Path(clean_name).stem).replace("_", " ").title()[:31]
        ws.title = sheet_title if sheet_title else "Sheet1"

        headers, rows = _parse_or_generate_spreadsheet_data(content, title or Path(clean_name).stem)

        header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        center_align = Alignment(horizontal="center", vertical="center")
        thin_border = Border(
            left=Side(style="thin", color="D9D9D9"),
            right=Side(style="thin", color="D9D9D9"),
            top=Side(style="thin", color="D9D9D9"),
            bottom=Side(style="thin", color="D9D9D9"),
        )
        alt_fill = PatternFill(start_color="F2F5F9", end_color="F2F5F9", fill_type="solid")

        # Headers
        ws.append(headers)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align

        # Rows
        for r_idx, row in enumerate(rows, start=2):
            ws.append(row)
            for c_idx in range(1, len(row) + 1):
                cell = ws.cell(row=r_idx, column=c_idx)
                cell.font = Font(name="Segoe UI", size=10)
                cell.border = thin_border
                if r_idx % 2 == 1:
                    cell.fill = alt_fill

        # Auto-adjust column widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        try:
            wb.save(str(file_path))
        except PermissionError:
            logger.warning(f"File '{file_path}' is locked by another process (e.g. Excel). Closing EXCEL to update spreadsheet...")
            try:
                import subprocess, time
                subprocess.run(["taskkill", "/F", "/IM", "EXCEL.EXE"], capture_output=True)
                time.sleep(0.35)
                wb.save(str(file_path))
            except Exception as pe:
                logger.error(f"Failed to overwrite locked spreadsheet after taskkill: {pe}")
                alt_name = f"{Path(clean_name).stem}_updated.xlsx"
                file_path = docs_dir / alt_name
                wb.save(str(file_path))
                clean_name = alt_name

        if open_after:
            try:
                os.startfile(str(file_path))
                return f"Created spreadsheet '{clean_name}' at {file_path} and opened in Microsoft Excel."
            except Exception as e:
                logger.warning(f"Could not automatically open created xlsx: {e}")
                return f"Created spreadsheet '{clean_name}' at {file_path}."

        return f"Created spreadsheet '{clean_name}' at {file_path}."
    except Exception as e:
        logger.error(f"Failed to create Excel spreadsheet: {e}")
        try:
            csv_name = (filename.replace(".xlsx", "").replace(".xls", "") if filename else "spreadsheet") + ".csv"
            csv_path = Path.home() / "Documents" / csv_name
            csv_path.write_text(content, encoding="utf-8")
            if open_after:
                os.startfile(str(csv_path))
            return f"Created spreadsheet CSV at {csv_path} and opened it."
        except Exception:
            return f"Failed to create spreadsheet: {e}"


def create_spreadsheet(filename: str, content: str = "", title: str = "", open_after: bool = True) -> str:
    """
    Create a formatted Microsoft Excel (.xlsx) spreadsheet and optionally open it.
    """
    return create_excel_spreadsheet(filename, content, title, open_after)


def create_office_document(filename: str, content: str, title: str = "", open_after: bool = True) -> str:
    """
    Create a formatted Microsoft Word (.docx) document, PowerPoint (.pptx) presentation, or Excel (.xlsx) spreadsheet and optionally open it.
    
    Args:
        filename: Name of the file (e.g. 'Leave_Application.docx', 'water_wastage.pptx', or 'students.xlsx').
        content: The body text, slides outline, or spreadsheet rows.
        title: Optional document heading / subject / sheet title.
        open_after: If True, opens the document in Microsoft Office immediately.
        
    Returns:
        Status message with the saved document path.
    """
    fn_lower = (filename or "").lower()
    is_presentation = (
        fn_lower.endswith(".pptx")
        or fn_lower.endswith(".ppt")
        or "slide" in (content or "").lower()[:120]
        or "presentation" in fn_lower
        or "ppt" in fn_lower
    )
    if is_presentation:
        return create_powerpoint_presentation(filename, content, title, open_after)

    is_spreadsheet = (
        fn_lower.endswith(".xlsx")
        or fn_lower.endswith(".xls")
        or fn_lower.endswith(".csv")
        or "excel" in fn_lower
        or "sheet" in fn_lower
        or "spreadsheet" in fn_lower
    )
    if is_spreadsheet:
        return create_excel_spreadsheet(filename, content, title, open_after)

    try:
        import docx
        from datetime import datetime

        clean_name = (filename or "document.docx").strip()
        if not clean_name.lower().endswith(".docx"):
            clean_name += ".docx"

        docs_dir = Path.home() / "Documents"
        docs_dir.mkdir(parents=True, exist_ok=True)
        file_path = docs_dir / clean_name

        doc = docx.Document()
        heading = title.strip() if title else "Document"
        doc.add_heading(heading, level=0)
        doc.add_paragraph(f"Date: {datetime.now().strftime('%B %d, %Y')}")

        for para in content.split("\n\n"):
            p_strip = para.strip()
            if p_strip:
                doc.add_paragraph(p_strip)

        try:
            doc.save(str(file_path))
        except PermissionError:
            logger.warning(f"File '{file_path}' is locked by another process (e.g. Word). Closing WINWORD to update document...")
            try:
                import subprocess
                import time
                subprocess.run(["taskkill", "/F", "/IM", "WINWORD.EXE"], capture_output=True)
                time.sleep(0.35)
                doc.save(str(file_path))
            except Exception as pe:
                logger.error(f"Failed to overwrite locked file after taskkill: {pe}")
                alt_name = f"{Path(clean_name).stem}_updated.docx"
                file_path = docs_dir / alt_name
                doc.save(str(file_path))
                clean_name = alt_name

        if open_after:
            try:
                os.startfile(str(file_path))
                return f"Created document '{clean_name}' at {file_path} and opened in Microsoft Office Word."
            except Exception as e:
                logger.warning(f"Could not automatically open created docx: {e}")
                return f"Created document '{clean_name}' at {file_path}."

        return f"Created document '{clean_name}' at {file_path}."
    except Exception as e:
        logger.error(f"Failed to create office document: {e}")
        # Safe fallback: create text document and open
        try:
            txt_name = (filename.replace(".docx", "") if filename else "document") + ".txt"
            txt_path = Path.home() / "Documents" / txt_name
            txt_path.write_text(content, encoding="utf-8")
            if open_after:
                os.startfile(str(txt_path))
            return f"Created document at {txt_path} and opened it."
        except Exception as ex:
            return f"Failed to create document: {e}"


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
    """Get current clipboard text contents safely."""
    try:
        import pyperclip
        val = pyperclip.paste()
        return val if val else "Clipboard is empty."
    except Exception:
        pass

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-Clipboard",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout.strip() if result.stdout else "Clipboard is empty."
    except Exception as e:
        return f"Error reading clipboard: {e}"


def set_clipboard(text: str) -> str:
    """Set clipboard text contents with full Unicode and emoji support without shell code injection."""
    # 1. Primary: Use pyperclip if available
    try:
        import pyperclip
        pyperclip.copy(text)
        return f"Copied to clipboard ({len(text)} chars)."
    except Exception:
        pass

    # 2. Native Windows clip.exe via binary stdin pipe (No shell, no executable code)
    try:
        subprocess.run(
            ["clip.exe"],
            input=text.encode("utf-16le"),
            timeout=5,
            check=True,
            capture_output=True,
        )
        return f"Copied to clipboard ({len(text)} chars)."
    except Exception:
        pass

    # 3. Safe PowerShell stdin stream fallback (Completely static command, data passed strictly via stdin stream)
    try:
        p = subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "[Console]::InputEncoding = [System.Text.Encoding]::UTF8; [Console]::In.ReadToEnd() | Set-Clipboard",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        p.communicate(input=text.encode("utf-8"), timeout=5)
        if p.returncode == 0:
            return f"Copied to clipboard ({len(text)} chars)."
        return f"PowerShell clipboard error (Exit {p.returncode})"
    except Exception as e:
        return f"Error setting clipboard: {e}"


# ═══════════════════════════════════════════════════════════
#  Window Focus & Desktop / Web App Message Typing
# ═══════════════════════════════════════════════════════════

WEB_APP_URLS = {
    "whatsapp": "https://web.whatsapp.com",
    "discord": "https://discord.com/app",
    "slack": "https://app.slack.com",
    "telegram": "https://web.telegram.org",
    "chatgpt": "https://chatgpt.com",
    "twitter": "https://twitter.com/messages",
    "x": "https://x.com/messages",
    "gmail": "https://mail.google.com",
}


def get_window_title(hwnd: int) -> str:
    """Get the window title for an HWND handle."""
    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(hwnd)
    if length > 0:
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value.strip()
    return ""


def get_open_windows(filter_query: str = "") -> list[tuple[int, str]]:
    """
    Get a list of all visible application windows (HWND, title).
    Uses standard Win32 EnumWindows with dual fallback to winsta0\\default
    to reliably capture windows across user desktop stations.
    """
    windows = []
    user32 = ctypes.windll.user32
    ignored = {"Program Manager", "Settings", "Default IME", "MSCTFIME UI", "Windows Input Experience"}

    def enum_cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            title = get_window_title(hwnd)
            if title and title not in ignored:
                if not filter_query or filter_query.lower() in title.lower():
                    windows.append((hwnd, title))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    try:
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    except Exception:
        pass

    # If empty (e.g. running from background session), query winsta0\\default
    if not windows:
        try:
            hwinsta = user32.OpenWindowStationW("winsta0", False, 0x037F)
            if hwinsta:
                hdesk = user32.OpenDesktopW("default", 0, False, 0x01FF)
                if hdesk:
                    DESKTOPENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                    user32.EnumDesktopWindows(hdesk, DESKTOPENUMPROC(enum_cb), 0)
        except Exception:
            pass

    return windows


def list_open_windows(query: str = "") -> str:
    """List all open application windows and web apps currently running on the desktop."""
    wins = get_open_windows(filter_query=query)
    if not wins:
        return "No visible open application windows found."

    lines = [f"Open Windows ({len(wins)}):"]
    for hwnd, title in wins:
        tag = ""
        title_lower = title.lower()
        if any(b in title_lower for b in ["chrome", "opera", "edge", "firefox", "brave"]):
            tag = " [Web Browser]"
        elif "whatsapp" in title_lower:
            tag = " [WhatsApp Web/App]"
        elif "discord" in title_lower:
            tag = " [Discord]"
        elif "slack" in title_lower:
            tag = " [Slack]"
        elif "chatgpt" in title_lower:
            tag = " [ChatGPT]"
        lines.append(f"  - {title}{tag}")

    return "\n".join(lines)


def focus_window_by_hwnd(hwnd: int) -> bool:
    """
    Bring a window to the foreground and grant it keyboard focus.
    Uses AttachThreadInput and simulated ALT key to bypass Windows SetForegroundWindow restrictions.
    """
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # Restore if minimized
    SW_RESTORE = 9
    user32.ShowWindow(hwnd, SW_RESTORE)

    current_thread_id = kernel32.GetCurrentThreadId()
    target_thread_id = user32.GetWindowThreadProcessId(hwnd, None)

    try:
        user32.AttachThreadInput(current_thread_id, target_thread_id, True)
    except Exception:
        pass

    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)

    try:
        user32.AttachThreadInput(current_thread_id, target_thread_id, False)
    except Exception:
        pass

    # Break foreground lock with brief ALT key tap
    user32.keybd_event(0x12, 0, 0, 0)
    user32.keybd_event(0x12, 0, 2, 0)
    user32.SetForegroundWindow(hwnd)
    return True


def find_window_by_name(target: str) -> tuple[int | None, str | None]:
    """Find a window HWND and title matching target app or keywords."""
    if not target:
        return None, None

    windows = get_open_windows()
    q = target.lower().strip()

    # 1. Exact or substring match in title
    for hwnd, title in windows:
        if q in title.lower():
            return hwnd, title

    # 2. Browser alias matching
    browser_keywords = ["chrome", "edge", "opera", "firefox", "brave"]
    if q in ("browser", "web", "internet"):
        for hwnd, title in windows:
            if any(b in title.lower() for b in browser_keywords):
                return hwnd, title

    # 3. Web app aliases
    if q in ("whatsapp", "wa"):
        for hwnd, title in windows:
            if "whatsapp" in title.lower():
                return hwnd, title
    if q in ("discord",):
        for hwnd, title in windows:
            if "discord" in title.lower():
                return hwnd, title
    if q in ("slack",):
        for hwnd, title in windows:
            if "slack" in title.lower():
                return hwnd, title
    if q in ("chatgpt", "gpt"):
        for hwnd, title in windows:
            if "chatgpt" in title.lower():
                return hwnd, title

    # 4. Office application aliases
    if q in ("word", "microsoft word", "ms word", "winword", "office", "microsoft office", "office 365"):
        for hwnd, title in windows:
            t_low = title.lower()
            if "word" in t_low or "document" in t_low:
                return hwnd, title
    if q in ("excel", "microsoft excel", "ms excel"):
        for hwnd, title in windows:
            t_low = title.lower()
            if "excel" in t_low or "workbook" in t_low or "sheet" in t_low:
                return hwnd, title
    if q in ("powerpoint", "microsoft powerpoint", "ms powerpoint", "ppt"):
        for hwnd, title in windows:
            t_low = title.lower()
            if "powerpoint" in t_low or "presentation" in t_low or "slide" in t_low:
                return hwnd, title
    if q in ("notepad",):
        for hwnd, title in windows:
            if "notepad" in title.lower():
                return hwnd, title

    return None, None


def minimize_window(title: str) -> str:
    """Minimize a window by title keyword."""
    hwnd, matched_title = find_window_by_name(title)
    if not hwnd:
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(title)
            if wins:
                wins[0].minimize()
                return f"Minimized window '{wins[0].title}'."
        except Exception as e:
            logger.debug(f"pygetwindow minimize fallback error: {e}")
        return f"Window matching '{title}' not found."

    try:
        SW_MINIMIZE = 6
        ctypes.windll.user32.ShowWindow(hwnd, SW_MINIMIZE)
        return f"Minimized window '{matched_title}'."
    except Exception as e:
        return f"Could not minimize window: {e}"


def maximize_window(title: str) -> str:
    """Maximize a window by title keyword."""
    hwnd, matched_title = find_window_by_name(title)
    if not hwnd:
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(title)
            if wins:
                wins[0].maximize()
                return f"Maximized window '{wins[0].title}'."
        except Exception as e:
            logger.debug(f"pygetwindow maximize fallback error: {e}")
        return f"Window matching '{title}' not found."

    try:
        SW_MAXIMIZE = 3
        ctypes.windll.user32.ShowWindow(hwnd, SW_MAXIMIZE)
        return f"Maximized window '{matched_title}'."
    except Exception as e:
        return f"Could not maximize window: {e}"


def snap_window(title: str, position: str) -> str:
    """Snap a window to the left or right half of the screen."""
    pos = position.lower().strip()
    if pos not in ("left", "right"):
        return f"Invalid snap position '{position}'. Use 'left' or 'right'."

    hwnd, matched_title = find_window_by_name(title)
    if not hwnd:
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(title)
            if wins:
                win = wins[0]
                screen_w = ctypes.windll.user32.GetSystemMetrics(0)
                screen_h = ctypes.windll.user32.GetSystemMetrics(1)
                half_w = screen_w // 2
                win.restore()
                if pos == "left":
                    win.moveTo(0, 0)
                    win.resizeTo(half_w, screen_h)
                else:
                    win.moveTo(half_w, 0)
                    win.resizeTo(half_w, screen_h)
                return f"Snapped '{win.title}' to the {position}."
        except Exception as e:
            return f"Failed to snap window: {e}"
        return f"Window matching '{title}' not found."

    try:
        screen_w = ctypes.windll.user32.GetSystemMetrics(0)
        screen_h = ctypes.windll.user32.GetSystemMetrics(1)
        half_w = screen_w // 2

        SW_RESTORE = 9
        ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
        x = 0 if pos == "left" else half_w
        ctypes.windll.user32.MoveWindow(hwnd, x, 0, half_w, screen_h, True)
        return f"Snapped '{matched_title}' to the {position}."
    except Exception as e:
        return f"Failed to snap window: {e}"


def type_message(message: str, app_name_or_title: str = "", press_enter: bool = False, delay_before: float = 0.25) -> str:
    """
    Type a message on behalf of the user into a web app or open desktop window.

    Brings the targeted application to the foreground, focuses its input field,
    pastes the message with 100% Unicode & emoji fidelity, and optionally presses Enter to send.

    Args:
        message: The message text to type.
        app_name_or_title: Target app name or window title keyword (e.g., 'WhatsApp', 'Discord', 'Slack', 'Chrome', 'Opera', 'ChatGPT', or '' for active window).
        press_enter: If True, press Enter after typing to send the message.
        delay_before: Seconds to pause after focusing before typing (default 0.25s).

    Returns:
        Confirmation status message.
    """
    import time
    user32 = ctypes.windll.user32
    target = app_name_or_title.strip()
    matched_title = None
    hwnd = None

    if target and target.lower() not in ("active", "current", "this", ""):
        hwnd, matched_title = find_window_by_name(target)
        if not hwnd:
            # Check if it's a known web app that isn't open yet
            app_key = target.lower()
            if app_key in WEB_APP_URLS:
                import webbrowser
                url = WEB_APP_URLS[app_key]
                webbrowser.open(url)
                time.sleep(1.5)
                hwnd, matched_title = find_window_by_name(target)
                if not hwnd:
                    hwnd, matched_title = find_window_by_name("browser")

            if not hwnd:
                open_wins = get_open_windows()
                sample = ", ".join(t for _, t in open_wins[:5]) if open_wins else "None"
                return f"Could not find an open window matching '{target}'. Currently open windows: {sample}"

        # Bring window to foreground
        focus_window_by_hwnd(hwnd)
        time.sleep(delay_before)
    else:
        # Use currently active window
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            matched_title = get_window_title(hwnd)
        else:
            matched_title = "Active Window"

    # Type the message using clipboard injection for 100% Unicode + emoji fidelity
    try:
        import pyperclip
        pyperclip.copy(message)
    except Exception:
        set_clipboard(message)

    time.sleep(0.05)

    # Simulate Ctrl+V to paste
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "v")
    except Exception:
        # Win32 keybd_event fallback
        VK_CONTROL = 0x11
        VK_V = 0x56
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_V, 0, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(VK_V, 0, 2, 0)
        user32.keybd_event(VK_CONTROL, 0, 2, 0)

    time.sleep(0.1)

    # Press Enter if requested
    if press_enter:
        time.sleep(0.1)
        try:
            import pyautogui
            pyautogui.press("enter")
        except Exception:
            VK_RETURN = 0x0D
            user32.keybd_event(VK_RETURN, 0, 0, 0)
            time.sleep(0.02)
            user32.keybd_event(VK_RETURN, 0, 2, 0)

    target_name = matched_title or target or "the active window"
    action = "typed and sent" if press_enter else "typed (ready to send)"
    return f"Successfully {action} message into '{target_name}':\n\n\"{message}\""


def send_web_message(platform: str, message: str, recipient: str = "", press_enter: bool = True) -> str:
    """
    Send a message to a web app (WhatsApp Web, Discord, Slack, Telegram, ChatGPT).

    Args:
        platform: Platform name ('whatsapp', 'discord', 'slack', 'telegram', 'chatgpt').
        message: The message to send.
        recipient: Optional recipient name or phone number (for WhatsApp).
        press_enter: Whether to hit Enter to send.
    """
    plat = platform.lower().strip()

    # WhatsApp Web special direct URL handling if not already open
    if "whatsapp" in plat:
        hwnd, title = find_window_by_name("whatsapp")
        if not hwnd and recipient:
            import urllib.parse
            phone_clean = "".join(c for c in recipient if c.isdigit() or c == "+")
            msg_encoded = urllib.parse.quote(message)
            if phone_clean:
                url = f"https://web.whatsapp.com/send?phone={phone_clean}&text={msg_encoded}"
            else:
                url = f"https://web.whatsapp.com/send?text={msg_encoded}"
            import webbrowser
            webbrowser.open(url)
            return f"Opened WhatsApp Web with pre-filled message for '{recipient}':\n\n\"{message}\"\n\nPress send when the chat loads!"

    # Otherwise type directly into the platform window
    return type_message(message=message, app_name_or_title=platform, press_enter=press_enter)


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
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "RemoteSigned", "-Command", ps_cmd],
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
        name="create_office_document",
        func=create_office_document,
        description="Create a formatted Microsoft Word (.docx) document (e.g. leave application, letter, notes) and automatically open it in Microsoft Office Word.",
        params={
            "filename": {"type": "string", "description": "Filename ending with .docx (e.g. 'Leave_Application.docx')", "default": "leave_letter.docx"},
            "content": {"type": "string", "description": "The complete formatted text or letter content to write"},
            "title": {"type": "string", "description": "Document title heading", "default": "Leave Application"},
            "open_after": {"type": "boolean", "description": "Whether to automatically open in Microsoft Office Word", "default": True},
        },
        required=["content"],
        category="office",
        security_level=SecurityLevel.SAFE,
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

    # ── E2B Isolated Sandbox Code Execution ───────────────────
    from services.sandbox.e2b_service import sandbox_service

    def _execute_python_code(code: str, timeout: int = 30) -> str:
        """Execute Python code inside an isolated E2B microVM sandbox."""
        res = sandbox_service.execute_code(code, timeout=timeout)
        if res.success:
            return res.stdout if res.stdout else "Code executed successfully (no output)."
        return f"Sandbox Error:\n{res.stderr or res.error_message}"

    def _execute_sandbox_command(command: str, timeout: int = 30) -> str:
        """Execute a shell command inside an isolated E2B microVM sandbox."""
        res = sandbox_service.execute_terminal_command(command, timeout=timeout)
        if res.success:
            return res.stdout if res.stdout else "Command completed (no output)."
        return f"Sandbox Command Error (Exit {res.exit_code}):\n{res.stderr or res.error_message}"

    registry.register(
        name="execute_python_code",
        func=_execute_python_code,
        description="Execute Python code safely inside an isolated E2B microVM sandbox. Recommended for all AI-generated scripts and data analysis.",
        params={
            "code": {"type": "string", "description": "Python source code to execute inside sandbox"},
            "timeout": {"type": "integer", "description": "Max execution time in seconds", "default": 30},
        },
        required=["code"],
        category="sandbox",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="execute_sandbox_command",
        func=_execute_sandbox_command,
        description="Execute a terminal command safely inside an isolated E2B microVM sandbox.",
        params={
            "command": {"type": "string", "description": "Terminal command to run inside sandbox"},
            "timeout": {"type": "integer", "description": "Max execution time in seconds", "default": 30},
        },
        required=["command"],
        category="sandbox",
        security_level=SecurityLevel.SAFE,
    )

    # ── Window Focus & Typing on Web / Apps ───────────────────
    registry.register(
        name="minimize_window",
        func=minimize_window,
        description="Minimize a desktop window by title",
        params={"title": {"type": "string", "description": "Window title keyword"}},
        required=["title"],
        category="system",
        security_level=SecurityLevel.SAFE,
    )
    registry.register(
        name="maximize_window",
        func=maximize_window,
        description="Maximize a desktop window by title",
        params={"title": {"type": "string", "description": "Window title keyword"}},
        required=["title"],
        category="system",
        security_level=SecurityLevel.SAFE,
    )
    registry.register(
        name="snap_window",
        func=snap_window,
        description="Snap a window to the left or right half of the screen",
        params={
            "title": {"type": "string", "description": "Window title keyword"},
            "position": {"type": "string", "enum": ["left", "right"], "description": "Snap target position"},
        },
        required=["title", "position"],
        category="system",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="type_message",
        func=type_message,
        description="Type a message on behalf of Dad into any web app (WhatsApp Web, Discord, Slack, ChatGPT, etc.) or open desktop window, optionally pressing Enter to send.",
        params={
            "message": {"type": "string", "description": "The exact message text to type"},
            "app_name_or_title": {"type": "string", "description": "Target web app or window name (e.g. 'whatsapp', 'discord', 'slack', 'chrome', 'opera', or '' for active window)", "default": ""},
            "press_enter": {"type": "boolean", "description": "Whether to press Enter after typing to send the message", "default": False},
        },
        required=["message"],
        category="automation",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="send_web_message",
        func=send_web_message,
        description="Send a message directly to a web chat platform (WhatsApp Web, Discord, Slack, Telegram, ChatGPT). Opens the chat or focuses the open window, pastes the message, and sends it.",
        params={
            "platform": {"type": "string", "description": "Target platform (e.g. 'whatsapp', 'discord', 'slack', 'telegram', 'chatgpt')"},
            "message": {"type": "string", "description": "The message to send"},
            "recipient": {"type": "string", "description": "Optional recipient name or phone number", "default": ""},
            "press_enter": {"type": "boolean", "description": "Whether to press Enter to send", "default": True},
        },
        required=["platform", "message"],
        category="automation",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="list_open_windows",
        func=list_open_windows,
        description="List all open windows and web applications currently running on the desktop.",
        params={
            "query": {"type": "string", "description": "Optional filter keyword for window titles", "default": ""},
        },
        category="system",
        security_level=SecurityLevel.SAFE,
    )

