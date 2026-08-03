# main.py — SON V3 Personal Computer Assistant Unified Entry Point
"""
SON V3 — The Personal Computer Assistant
Usage:
    python main.py              Start PySide6 Desktop GUI Dashboard
    python main.py --cli        Start in Terminal CLI mode
    python main.py --voice      Start in Voice-First mode
    python main.py --wakeword   Start with wake word detection ("Hey SON")
    python main.py --list-tools List all registered plugins and tools
"""
import sys
import os
import argparse

# Fix Windows console UTF-8 encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from core.config import Config
from core.state import SystemState
from core.router import IntentRouter
from core.brain import Brain

from plugins import PluginRegistry
from plugins.windows import WindowsPlugin
from plugins.files import FilesPlugin
from plugins.vscode import VSCodePlugin
from plugins.docker import DockerPlugin
from plugins.browser import BrowserPlugin
from plugins.spotify import SpotifyPlugin
from plugins.weather import WeatherPlugin


def list_tools():
    registry = PluginRegistry()
    registry.register_plugin(WindowsPlugin())
    registry.register_plugin(FilesPlugin())
    registry.register_plugin(VSCodePlugin())
    registry.register_plugin(DockerPlugin())
    registry.register_plugin(BrowserPlugin())
    registry.register_plugin(SpotifyPlugin())
    registry.register_plugin(WeatherPlugin())

    print(f"\nRegistered Tools for SON V3 ({registry.count()} total):\n")
    for t in registry.list_tools():
        print(f"  • [{t['plugin'].upper():<8s}] [{t['security_level'].upper():<9s}] {t['name']:<28s} — {t['description'][:60]}")
    print()


def run_cli(voice_mode=False, wakeword_mode=False):
    from son import Son
    son_app = Son(voice_mode=voice_mode, wakeword_mode=wakeword_mode)
    son_app.run()


def run_gui():
    from PySide6.QtWidgets import QApplication
    from gui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


def main():
    parser = argparse.ArgumentParser(description="SON V3 — Personal Computer Assistant")
    parser.add_argument("--cli", action="store_true", help="Start in terminal CLI mode")
    parser.add_argument("--voice", "-v", action="store_true", help="Start in voice-first mode")
    parser.add_argument("--wakeword", "-w", action="store_true", help="Start with wake word listener ('Hey SON')")
    parser.add_argument("--list-tools", action="store_true", help="List all registered tools and exit")

    args = parser.parse_args()

    if args.list_tools:
        list_tools()
        return

    if args.cli or args.voice or args.wakeword:
        run_cli(voice_mode=args.voice, wakeword_mode=args.wakeword)
    else:
        try:
            import PySide6
            run_gui()
        except ImportError:
            print("PySide6 is not installed yet. Defaulting to CLI mode...")
            run_cli(voice_mode=args.voice, wakeword_mode=args.wakeword)


if __name__ == "__main__":
    main()
