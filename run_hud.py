# run_hud.py — Standalone Launcher for SON V3 Holographic Ambient HUD
"""
Launch SON V3 with full movie-grade Ambient Holographic HUD:
    python run_hud.py
"""
import sys
import os
import threading
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from hud import HolographicHUDWindow, HUDState, HUDEventBridge


def start_son_background(bridge: HUDEventBridge):
    """Run the SON conversational loop connected to HUD."""
    from son import Son
    app_son = Son(voice_mode=False, hud_mode=True)

    # Attach bridge callbacks to SON
    time.sleep(1.0)
    bridge.notify_state(HUDState.IDLE, "SYSTEM ONLINE")
    bridge.notify_subtitle("SON", "Welcome back, Dad. All systems nominal.")

    # Start conversational loop in background
    app_son.run()


def main():
    # Force UTF-8 on Windows
    if sys.platform == "win32":
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Create & Show Holographic HUD Window
    hud_window = HolographicHUDWindow()
    hud_window.show()

    # Launch SON background orchestrator
    bridge = HUDEventBridge.get_instance()
    t = threading.Thread(target=start_son_background, args=(bridge,), daemon=True, name="SON-Orchestrator")
    t.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
