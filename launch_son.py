# launch_son.py — Master Launcher for SON V3 (Python Backend + Godot Frontend)
"""
Master Launcher for SON V3:
1. Starts the WebSocket IPC Server (ws://127.0.0.1:8765)
2. Initializes the Python AI Engine (Ollama, Memory, Voice, Vision, Tools)
3. Launches Godot 4 Holographic 3D Frontend (with PySide6 HUD fallback)
"""
import sys
import os
import time
import subprocess
import threading
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ipc.server import SONIPCServer
from ipc.protocol import VisualState
from son import Son

def find_godot_executable() -> str | None:
    """Check for Godot executable or exported Windows frontend binary."""
    candidates = [
        Path(r"c:\AI\SON\godot_frontend\bin\SON_HUD.exe"),
        Path(r"c:\AI\SON\godot_frontend\SON_HUD.exe"),
        Path(r"C:\Program Files\Godot\Godot_v4.3-stable_win64.exe"),
        Path(r"C:\Godot\godot.exe"),
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    # Check PATH
    import shutil
    godot_in_path = shutil.which("godot") or shutil.which("godot4")
    if godot_in_path:
        return godot_in_path
    return None

def main():
    print("=" * 65)
    print("      SON V3  ::  MASTER ORCHESTRATOR LAUNCHER")
    print("=" * 65)

    # 1. Start WebSocket IPC Server
    ipc = SONIPCServer.get_instance()
    ipc.start()
    print("✓ WebSocket IPC Server running on ws://127.0.0.1:8765")

    # 2. Check for Godot Frontend
    godot_exe = find_godot_executable()
    godot_proc = None

    if godot_exe:
        print(f"✓ Found Godot Engine: {godot_exe}")
        project_path = str(Path(r"c:\AI\SON\godot_frontend\project.godot"))
        godot_proc = subprocess.Popen([godot_exe, "--path", str(Path(r"c:\AI\SON\godot_frontend"))])
        print("✓ Launched Godot 4 Holographic Ambient Frontend!")
    else:
        print("ℹ Godot binary not found in standard paths. Launching PySide6 Holographic Ambient HUD...")
        # Start PySide6 HUD in separate process
        hud_proc = subprocess.Popen([sys.executable, str(Path(__file__).parent / "run_hud.py")])

    # 3. Start Python AI Backend
    print("✓ Initializing SON AI Brain & Voice pipeline...")
    son_app = Son(voice_mode=False, hud_mode=True)

    # Hook inbound prompt handler from Godot into SON
    def on_inbound_prompt(data: dict):
        text = data.get("text", "")
        if text:
            threading.Thread(target=son_app._respond, args=(text,), daemon=True).start()

    def on_inbound_voice_trigger(_data: dict):
        threading.Thread(target=son_app._get_voice_input, daemon=True).start()

    ipc.register_handler("user_prompt", on_inbound_prompt)
    ipc.register_handler("voice_trigger", on_inbound_voice_trigger)

    # Run AI conversation loop
    try:
        son_app.run()
    finally:
        ipc.stop()
        if godot_proc:
            godot_proc.terminate()

if __name__ == "__main__":
    main()
