# SON V3 — Windows Automation Architecture

## 1. Overview
In Phase 2, SON V3 transitions from a conversational chatbot into a deterministic Windows 11 PC controller.
All Windows desktop actions execute via **Tier 1 Native Windows APIs** or **Tier 2 Controlled Shell Runners**, coordinated centrally by `HostAgent` and `ExecutionRouter`.

```
User Request
    │
HostAgent
    │
Intent Classification
    │
ExecutionRouter
 ├── Tier 1 (Native Win32, psutil, ctypes, pathlib)
 ├── Tier 2 (Controlled CLI & PowerShell runner)
 ├── Tier 3 (Windows UI Automation — Phase 3)
 └── Tier 4 (Visual Computer Use — Phase 4)
```

---

## 2. Tier 1 Native Windows Integration

### A. Application Lifecycle (`core/execution/tier1_native/process.py`)
- **Discovery**: Dynamically resolves executables across `%ProgramFiles%`, `%ProgramFiles(x86)%`, `%LOCALAPPDATA%\Programs`, and trusted system directories.
- **Approved Registry**: Validates application identity against `APPROVED_APP_DISCOVERY` (Chrome, Edge, Firefox, VS Code, Notepad, Calculator, Spotify, Docker, Ollama, VirtualBox, Terminal).
- **Process Supervision**: Tracks PIDs, inspects CPU/RAM utilization, and performs graceful termination (`SIGTERM`) or forced termination (`SIGKILL`).

### B. Window Management (`core/execution/tier1_native/windows.py`)
- Direct Win32 APIs via `ctypes.windll.user32`.
- `list_windows()`: Enumerates visible desktop windows, filtering out tooltips and cloaked system utility frames. Falls back to `winsta0\default` across desktop stations.
- `get_active_window()`: Retrieves HWND, title, and PID of the foreground window.
- Window State Control: `minimize_window`, `maximize_window`, `restore_window`, `activate_window`.
- Screen Snapping: `snap_window` dynamically calculates work area dimensions (respecting the Windows taskbar) and snaps windows to `left`, `right`, `top`, `bottom`, or `full`.

### C. Native Filesystem Operations (`core/execution/tier1_native/filesystem.py`)
- **Canonical Path Resolution**: Uses `Path.resolve()` to normalize all paths and resolve symlinks.
- **Directory Traversal Defense**: Blocks directory escape attempts (`..`) and Zip-Slip attacks in archive extractions.
- **Protected Areas**: Blocks modifications and deletions targeted at `C:\Windows`, `C:\Program Files`, `C:\Users` root, and drive roots (`C:\`).
- **High-Impact Gate**: Permanent deletions strictly require explicit user approval.

### D. System Telemetry & Hardware (`core/execution/tier1_native/system.py`)
- **NVML GPU Monitoring**: Queries NVIDIA GeForce RTX 4060 Laptop GPU metrics directly in-process via C bindings (`pynvml`), avoiding expensive `nvidia-smi` subprocess spawns.
- **Telemetry Cache**: Caches non-critical metrics with a 2.5s TTL to prevent CPU polling overhead.
- **Hardware Controls**: Volume adjustment, mute/unmute, screen brightness, workstation lock, and scheduled shutdown/restart.
