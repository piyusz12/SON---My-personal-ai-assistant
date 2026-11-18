---
name: windows
description: Native Windows OS window and application controls via Tier 1 APIs.
version: 1.0.0
---

# Windows Management Skill

Provides deterministic, permission-controlled Windows desktop interaction without invoking arbitrary shell scripts.

## Capabilities
- **Application Lifecycle**: Launch approved desktop applications (`Chrome`, `VS Code`, `Edge`, `Spotify`, `Notepad`, etc.) via `NativeProcessManager`.
- **Window Management**: Enumerate visible windows, activate/focus, minimize, maximize, restore, and snap to screen halves or full screen.
- **Process Supervision**: Check if processes are running and close them gracefully.

## Execution Tier
- **Tier 1 (Native)**: Direct Win32 APIs (user32.dll) and psutil.
