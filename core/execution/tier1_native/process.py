# core/execution/tier1_native/process.py — Tier 1 Native Application & Process Management
"""
Manages Windows application lifecycle and processes natively via Win32, psutil, and registry discovery.
Validates applications against an approved registry and discovers installation paths dynamically.
"""
import glob
import logging
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import psutil

logger = logging.getLogger(__name__)

# Master Approved Application Registry with discovery candidates
APPROVED_APP_DISCOVERY: Dict[str, Dict[str, Any]] = {
    "chrome": {
        "exe_names": ["chrome.exe"],
        "paths": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ],
        "display_name": "Google Chrome",
    },
    "edge": {
        "exe_names": ["msedge.exe"],
        "paths": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "display_name": "Microsoft Edge",
    },
    "firefox": {
        "exe_names": ["firefox.exe"],
        "paths": [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ],
        "display_name": "Mozilla Firefox",
    },
    "vscode": {
        "exe_names": ["code.exe", "code.cmd"],
        "paths": [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
            r"C:\Program Files\Microsoft VS Code\Code.exe",
        ],
        "display_name": "Visual Studio Code",
    },
    "notepad": {
        "exe_names": ["notepad.exe"],
        "paths": [r"C:\Windows\System32\notepad.exe", r"C:\Windows\notepad.exe"],
        "display_name": "Notepad",
    },
    "calculator": {
        "exe_names": ["calc.exe", "CalculatorApp.exe"],
        "paths": [r"C:\Windows\System32\calc.exe"],
        "display_name": "Calculator",
    },
    "terminal": {
        "exe_names": ["wt.exe"],
        "paths": [
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe"),
            r"C:\Program Files\WindowsApps\Microsoft.WindowsTerminal*\wt.exe",
        ],
        "display_name": "Windows Terminal",
    },
    "spotify": {
        "exe_names": ["spotify.exe"],
        "paths": [
            os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe"),
        ],
        "display_name": "Spotify",
    },
    "docker": {
        "exe_names": ["Docker Desktop.exe"],
        "paths": [r"C:\Program Files\Docker\Docker\Docker Desktop.exe"],
        "display_name": "Docker Desktop",
    },
    "ollama": {
        "exe_names": ["ollama.exe", "ollama app.exe"],
        "paths": [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
        ],
        "display_name": "Ollama",
    },
    "virtualbox": {
        "exe_names": ["VirtualBox.exe"],
        "paths": [r"C:\Program Files\Oracle\VirtualBox\VirtualBox.exe"],
        "display_name": "Oracle VM VirtualBox",
    },
    "explorer": {
        "exe_names": ["explorer.exe"],
        "paths": [r"C:\Windows\explorer.exe"],
        "display_name": "Windows Explorer",
    },
    "taskmgr": {
        "exe_names": ["taskmgr.exe"],
        "paths": [r"C:\Windows\System32\taskmgr.exe"],
        "display_name": "Task Manager",
    },
    "paint": {
        "exe_names": ["mspaint.exe"],
        "paths": [r"C:\Windows\System32\mspaint.exe"],
        "display_name": "Paint",
    },
}

# Aliases mapping alternative names to canonical app keys
APP_ALIASES: Dict[str, str] = {
    "vs code": "vscode",
    "visual studio code": "vscode",
    "google chrome": "chrome",
    "ms edge": "edge",
    "microsoft edge": "edge",
    "calc": "calculator",
    "windows terminal": "terminal",
    "wt": "terminal",
    "file explorer": "explorer",
    "docker desktop": "docker",
    "task manager": "taskmgr",
}


class NativeProcessManager:
    """Tier 1 Process and Application Lifecycle Manager."""

    def __init__(self):
        self._path_cache: Dict[str, str] = {}

    def resolve_app_key(self, name: str) -> str:
        clean = name.strip().lower()
        return APP_ALIASES.get(clean, clean)

    def is_app_approved(self, name: str) -> bool:
        key = self.resolve_app_key(name)
        return key in APPROVED_APP_DISCOVERY

    def find_executable(self, name: str) -> Optional[str]:
        """Dynamically discover the executable path for an approved app."""
        key = self.resolve_app_key(name)
        if key in self._path_cache and os.path.exists(self._path_cache[key]):
            return self._path_cache[key]

        app_info = APPROVED_APP_DISCOVERY.get(key)
        if not app_info:
            return None

        # 1. Check known file paths
        for path_pattern in app_info.get("paths", []):
            if "*" in path_pattern:
                matches = glob.glob(path_pattern)
                if matches and os.path.exists(matches[0]):
                    self._path_cache[key] = matches[0]
                    return matches[0]
            elif os.path.exists(path_pattern):
                self._path_cache[key] = path_pattern
                return path_pattern

        # 2. Check PATH via shutil.which for each exe name
        for exe in app_info.get("exe_names", []):
            resolved = shutil.which(exe)
            if resolved and os.path.exists(resolved):
                self._path_cache[key] = resolved
                return resolved

        return None

    def launch_app(self, name: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Launch an approved application safely.
        Validates against the approved registry and resolves executable path.
        """
        key = self.resolve_app_key(name)
        if not self.is_app_approved(key):
            return {
                "success": False,
                "error": f"Security Error: Application '{name}' is not in the approved application registry.",
                "app_name": name,
            }

        exe_path = self.find_executable(key)
        if not exe_path:
            return {
                "success": False,
                "error": f"Application '{name}' is approved but its executable could not be found on this system.",
                "app_name": name,
            }

        cmd = [exe_path] + (args or [])
        try:
            proc = subprocess.Popen(
                cmd,
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
            # Short sleep to check if the process spawned or immediately died
            time.sleep(0.2)
            poll = proc.poll()
            if poll is not None and poll != 0:
                return {
                    "success": False,
                    "error": f"Application '{name}' exited immediately with code {poll}.",
                    "app_name": name,
                }

            return {
                "success": True,
                "app_name": name,
                "pid": proc.pid,
                "executable": exe_path,
                "message": f"Successfully launched {APPROVED_APP_DISCOVERY[key]['display_name']} (PID: {proc.pid}).",
            }
        except Exception as e:
            logger.exception(f"Failed to launch app '{name}': {e}")
            return {"success": False, "error": f"Failed to launch '{name}': {e}", "app_name": name}

    def is_app_running(self, name: str) -> Dict[str, Any]:
        """Check if an application is currently running by name or exe."""
        key = self.resolve_app_key(name)
        app_info = APPROVED_APP_DISCOVERY.get(key, {})
        target_exes = [e.lower() for e in app_info.get("exe_names", [name.lower()])]

        running_pids = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = (proc.info["name"] or "").lower()
                if pname in target_exes or any(pname.startswith(t.replace(".exe", "")) for t in target_exes):
                    running_pids.append(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        is_running = len(running_pids) > 0
        return {
            "success": True,
            "app_name": name,
            "running": is_running,
            "pids": running_pids,
            "count": len(running_pids),
        }

    def get_process_info(self, name_or_pid: Any) -> Dict[str, Any]:
        """Retrieve detailed process information for PID or process name."""
        try:
            if isinstance(name_or_pid, int) or (isinstance(name_or_pid, str) and name_or_pid.isdigit()):
                proc = psutil.Process(int(name_or_pid))
                return {
                    "success": True,
                    "pid": proc.pid,
                    "name": proc.name(),
                    "exe": proc.exe() if hasattr(proc, "exe") else None,
                    "status": proc.status(),
                    "cpu_percent": proc.cpu_percent(interval=0.05),
                    "memory_mb": round(proc.memory_info().rss / (1024 * 1024), 2),
                    "create_time": proc.create_time(),
                }
            else:
                target_name = str(name_or_pid).lower()
                matching = []
                for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
                    try:
                        pname = (p.info["name"] or "").lower()
                        if target_name in pname:
                            mem_mb = round(p.info["memory_info"].rss / (1024 * 1024), 2) if p.info["memory_info"] else 0
                            matching.append({
                                "pid": p.info["pid"],
                                "name": p.info["name"],
                                "memory_mb": mem_mb,
                            })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                return {
                    "success": True,
                    "query": str(name_or_pid),
                    "count": len(matching),
                    "processes": matching,
                }
        except psutil.NoSuchProcess:
            return {"success": False, "error": f"Process '{name_or_pid}' does not exist."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def close_app(self, name: str, force: bool = False) -> Dict[str, Any]:
        """Close running application safely (SIGTERM) or forcefully (SIGKILL)."""
        key = self.resolve_app_key(name)
        app_info = APPROVED_APP_DISCOVERY.get(key, {})
        target_exes = [e.lower() for e in app_info.get("exe_names", [name.lower()])]

        terminated_pids = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = (proc.info["name"] or "").lower()
                if pname in target_exes or any(pname.startswith(t.replace(".exe", "")) for t in target_exes):
                    if force:
                        proc.kill()
                    else:
                        proc.terminate()
                    terminated_pids.append(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not terminated_pids:
            return {"success": True, "message": f"No running processes found for '{name}'.", "terminated_count": 0}

        return {
            "success": True,
            "message": f"Closed '{name}' (terminated {len(terminated_pids)} process(es)).",
            "terminated_pids": terminated_pids,
            "terminated_count": len(terminated_pids),
        }

    def list_processes(self, limit: int = 50, sort_by: str = "memory") -> Dict[str, Any]:
        """List running processes sorted by memory or CPU usage."""
        procs = []
        for p in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                mem_mb = round(p.info["memory_info"].rss / (1024 * 1024), 2) if p.info["memory_info"] else 0
                procs.append({
                    "pid": p.info["pid"],
                    "name": p.info["name"],
                    "memory_mb": mem_mb,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if sort_by == "memory":
            procs.sort(key=lambda x: x["memory_mb"], reverse=True)
        else:
            procs.sort(key=lambda x: x["name"].lower())

        return {
            "success": True,
            "count": len(procs[:limit]),
            "total_running": len(procs),
            "processes": procs[:limit],
        }


# Singleton instance
native_process = NativeProcessManager()
