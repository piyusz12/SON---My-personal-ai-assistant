# gui/main_window.py — Futuristic PySide6 Desktop GUI Dashboard for SON V3
import sys
import threading
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QFrame, QMessageBox, QApplication
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QIcon, QColor

from core.config import Config, SecurityLevel
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

from agents.voice_agent import VoiceAgent
from agents.internet_agent import InternetAgent

from gui.widgets.orb import VoiceOrbWidget
from gui.widgets.system_monitor import SystemMonitorWidget
from gui.widgets.chat_view import ChatViewWidget
from gui.widgets.status_bar import StatusBarWidget


class MainWindow(QMainWindow):
    """
    Main PySide6 GUI Dashboard for SON V3.
    """
    response_ready = Signal(str, str)
    telemetry_signal = Signal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SON V3 — Personal Desktop Assistant")
        self.resize(1100, 720)
        self._init_theme()

        # Core Systems
        self.state = SystemState()
        self.plugins = PluginRegistry()

        # Register Plugins
        self.plugins.register_plugin(WindowsPlugin())
        self.plugins.register_plugin(FilesPlugin())
        self.plugins.register_plugin(VSCodePlugin())
        self.plugins.register_plugin(DockerPlugin())
        self.plugins.register_plugin(BrowserPlugin())
        self.plugins.register_plugin(SpotifyPlugin())
        self.plugins.register_plugin(WeatherPlugin())

        # Router & Brain
        self.router = IntentRouter(plugin_registry=self.plugins, state=self.state, ui_confirm_fn=self.security_confirm)
        self.brain = Brain(plugin_registry=self.plugins, router=self.router)
        self.voice = VoiceAgent(state=self.state)
        self.internet = InternetAgent(plugin_registry=self.plugins, state=self.state)

        # UI Setup
        self._init_ui()

        # Signals
        self.response_ready.connect(self._on_response_ready)
        self.telemetry_signal.connect(self._on_telemetry_update)

        # State Telemetry Subscriber
        self.state.subscribe(self._state_listener)
        self.state.start_monitoring(interval=1.5)

        # Initial Greeting
        QTimer.singleShot(500, self._initial_greeting)

    def _init_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0b0f19;
            }
            QWidget {
                font-family: 'Segoe UI', sans-serif;
            }
        """)

    def _init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Splitter Layout: Left Sidebar & Right Chat
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background-color: #1f2937; }")

        # ── Left Sidebar ───────────────────────────────────────
        left_panel = QWidget()
        left_panel.setMaximumWidth(320)
        left_panel.setStyleSheet("background-color: #111827; border-right: 1px solid #1f2937;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 15, 10, 10)

        # Voice Orb
        self.orb = VoiceOrbWidget()
        left_layout.addWidget(self.orb, alignment=Qt.AlignCenter)

        # Hardware Telemetry Gauge
        self.monitor = SystemMonitorWidget()
        left_layout.addWidget(self.monitor)

        # Quick Actions
        left_layout.addWidget(self._create_quick_actions())

        left_layout.addStretch()
        splitter.addWidget(left_panel)

        # ── Right Main Area ───────────────────────────────────
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Chat View
        self.chat_view = ChatViewWidget()
        self.chat_view.send_prompt.connect(self._on_user_prompt)
        self.chat_view.voice_toggled.connect(self._on_voice_toggle)
        right_layout.addWidget(self.chat_view)

        # Status Bar
        self.status_bar = StatusBarWidget()
        right_layout.addWidget(self.status_bar)

        splitter.addWidget(right_panel)
        splitter.setSizes([300, 800])

        main_layout.addWidget(splitter)
        self.setCentralWidget(main_widget)

    def _create_quick_actions() -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 5, 0, 5)

        btn_brief = QPushButton("🌅 Morning Briefing")
        btn_brief.setStyleSheet(self._btn_style("#3b82f6"))
        btn_brief.clicked.connect(self._cmd_morning_brief)

        btn_sys = QPushButton("💻 System Status")
        btn_sys.setStyleSheet(self._btn_style("#8b5cf6"))
        btn_sys.clicked.connect(self._cmd_system_status)

        btn_docker = QPushButton("🐳 Docker List")
        btn_docker.setStyleSheet(self._btn_style("#06b6d4"))
        btn_docker.clicked.connect(self._cmd_docker_list)

        layout.addWidget(btn_brief)
        layout.addWidget(btn_sys)
        layout.addWidget(btn_docker)
        return panel

    @staticmethod
    def _btn_style(color: str) -> str:
        return f"""
            QPushButton {{
                background-color: #1f2937;
                color: #f3f4f6;
                border: 1px solid {color};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: white;
            }}
        """

    def security_confirm(self, message: str, level: SecurityLevel) -> bool:
        """Show GUI Security Confirmation Dialog."""
        msg = QMessageBox(self)
        msg.setWindowTitle(f"Security Alert — {level.value.upper()}")
        msg.setText(message)
        msg.setIcon(QMessageBox.Warning)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        return msg.exec() == QMessageBox.Yes

    def _initial_greeting(self):
        tool_cnt = self.plugins.count()
        greeting = (
            f"Hello Piyush! I am **SON V3: The Personal Computer Assistant**.\n"
            f"I have **{tool_cnt} tools** loaded across 7 plugins (Windows, Files, VS Code, Docker, Web, Media, Weather).\n"
            f"How can I assist you with your desktop today?"
        )
        self.chat_view.append_message("SON", greeting, color="#a78bfa")

    def _on_user_prompt(self, prompt: str):
        self.orb.set_state("thinking")
        threading.Thread(target=self._process_prompt_thread, args=(prompt,), daemon=True).start()

    def _process_prompt_thread(self, prompt: str):
        try:
            response = self.brain.think(prompt)
            self.response_ready.emit("SON", response)
        except Exception as e:
            self.response_ready.emit("Error", str(e))

    @Slot(str, str)
    def _on_response_ready(self, sender: str, text: str):
        self.orb.set_state("idle")
        self.chat_view.append_message(sender, text, color="#a78bfa" if sender == "SON" else "#f87171")

    def _on_voice_toggle(self):
        self.orb.set_state("listening")
        threading.Thread(target=self._voice_record_thread, daemon=True).start()

    def _voice_record_thread(self):
        audio = self.voice.record_vad()
        if audio is not None:
            self.orb.set_state("thinking")
            text = self.voice.transcribe(audio)
            if text:
                self.response_ready.emit("You (Voice)", text)
                self._process_prompt_thread(text)
                return
        self.orb.set_state("idle")

    def _state_listener(self, event: str, data: any):
        if event == "telemetry_update":
            self.telemetry_signal.emit(data)

    @Slot(dict)
    def _on_telemetry_update(self, data: dict):
        self.monitor.update_metrics(data)
        self.status_bar.update_services(data)

    def _cmd_morning_brief(self):
        brief = self.internet.generate_daily_briefing()
        self.chat_view.append_message("SON Briefing", brief, color="#60a5fa")

    def _cmd_system_status(self):
        info = self.plugins.call("get_system_info", {})
        self.chat_view.append_message("System Telemetry", info, color="#34d399")

    def _cmd_docker_list(self):
        containers = self.plugins.call("docker_list_containers", {})
        self.chat_view.append_message("Docker Containers", containers, color="#06b6d4")

    def closeEvent(self, event):
        self.state.stop_monitoring()
        event.accept()
