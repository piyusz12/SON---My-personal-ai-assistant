# hud/main_window.py — Holographic Ambient HUD Window for SON V3
"""
Movie-grade Ambient HUD Overlay for SON V3:
- Frameless, translucent dark glassmorphism
- Real-time 60 FPS central holographic AI Orb
- Surrounding system diagnostics and perception panels
- Step-by-step thought & execution pipeline visualizer
- Hotkey toggle (F11 for Fullscreen Holographic Mode / Compact Desktop Overlay)
- Drag-and-drop movement anywhere on screen
"""
import sys
import psutil
import threading
from PySide6.QtCore import Qt, QTimer, QPoint, QRectF
from PySide6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGraphicsDropShadowEffect, QApplication
)

from hud.state import HUDState
from hud.orb import HolographicOrbWidget
from hud.panels import SystemHUDWidget, PerceptionHUDWidget, ActionPipelineWidget, SubtitleBannerWidget
from hud.bridge import HUDEventBridge


class HolographicHUDWindow(QMainWindow):
    """
    Main Floating Ambient Holographic HUD.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SON V3 — Holographic Ambient HUD")

        # Window Flags: Frameless, Translucent, Always on Top
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.SubWindow
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(1020, 560)

        # Dragging State
        self._drag_pos = QPoint()
        self._is_fullscreen = False

        # Central Event Bridge
        self.bridge = HUDEventBridge.get_instance()

        # Build UI Layout
        self._init_ui()

        # Connect Signals
        self._connect_bridge()

        # 60 FPS Animation Timer (~16.6ms)
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._on_tick)
        self._anim_timer.start(16)

        # 1.5s System Telemetry Poller
        self._telemetry_timer = QTimer(self)
        self._telemetry_timer.timeout.connect(self._poll_telemetry)
        self._telemetry_timer.start(1500)

        # Shortcuts
        self._shortcut_f11 = QShortcut(QKeySequence("F11"), self)
        self._shortcut_f11.activated.connect(self.toggle_fullscreen_mode)

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 12, 16, 16)
        main_layout.setSpacing(10)

        # ── 1. Top HUD Header Bar ──────────────────────────────
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 0, 10, 0)

        title_label = QLabel("◉  SON V3  ::  HOLOGRAPHIC AMBIENT INTERFACE")
        title_label.setFont(QFont("Consolas", 9, QFont.Bold))
        title_label.setStyleSheet("color: #00f0ff; letter-spacing: 2px;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        mode_btn = QPushButton("TOGGLE HUD [F11]")
        mode_btn.setFont(QFont("Consolas", 8, QFont.Bold))
        mode_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 240, 255, 30);
                color: #00f0ff;
                border: 1px solid rgba(0, 240, 255, 100);
                border-radius: 4px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: rgba(0, 240, 255, 70);
                color: #ffffff;
            }
        """)
        mode_btn.clicked.connect(self.toggle_fullscreen_mode)
        header_layout.addWidget(mode_btn)

        close_btn = QPushButton("✕")
        close_btn.setFont(QFont("Consolas", 9, QFont.Bold))
        close_btn.setFixedSize(26, 24)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 50, 70, 40);
                color: #ff3366;
                border: 1px solid rgba(255, 50, 70, 100);
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(255, 50, 70, 150);
                color: #ffffff;
            }
        """)
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)

        main_layout.addLayout(header_layout)

        # ── 2. Middle Tier: Left Panel | Orb | Right Panel ─────
        mid_layout = QHBoxLayout()
        mid_layout.setSpacing(20)

        # Left: System Diagnostics HUD
        self.sys_widget = SystemHUDWidget(self)
        mid_layout.addWidget(self.sys_widget, alignment=Qt.AlignVCenter)

        # Center: Interactive Holographic AI Orb
        self.orb_widget = HolographicOrbWidget(self, size=340)
        mid_layout.addWidget(self.orb_widget, alignment=Qt.AlignCenter)

        # Right: Optical Perception HUD
        self.percept_widget = PerceptionHUDWidget(self)
        mid_layout.addWidget(self.percept_widget, alignment=Qt.AlignVCenter)

        main_layout.addLayout(mid_layout)

        # ── 3. Action Execution Pipeline ───────────────────────
        self.pipeline_widget = ActionPipelineWidget(self)
        main_layout.addWidget(self.pipeline_widget, alignment=Qt.AlignCenter)

        # ── 4. Glowing Dialogue Subtitles ──────────────────────
        self.subtitle_widget = SubtitleBannerWidget(self)
        main_layout.addWidget(self.subtitle_widget)

    def _connect_bridge(self):
        """Connect thread-safe Qt signals from the bridge."""
        self.bridge.sig_state_changed.connect(self._on_bridge_state)
        self.bridge.sig_audio_level.connect(self.orb_widget.set_audio_level)
        self.bridge.sig_pipeline_stage.connect(self.pipeline_widget.set_pipeline_stage)
        self.bridge.sig_subtitle.connect(self.subtitle_widget.set_subtitle)
        self.bridge.sig_perception_update.connect(self.percept_widget.update_perception)
        self.bridge.sig_metrics_update.connect(self.sys_widget.update_metrics)
        self.bridge.sig_toggle_fullscreen.connect(lambda fs: self.set_fullscreen(fs))

    def _on_bridge_state(self, state: HUDState, activity_text: str):
        self.orb_widget.set_state(state, activity_text)

    def _on_tick(self):
        """Advance physics and paint every 16ms."""
        self.orb_widget.tick()

    def _poll_telemetry(self):
        """Collect live CPU, GPU (RTX 4060), and VRAM metrics in background."""
        def fetch():
            try:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory()
                ram_gb = ram.used / (1024 ** 3)

                gpu_util = 3.0
                vram_gb = 4.5
                try:
                    import pynvml
                    pynvml.nvmlInit()
                    h = pynvml.nvmlDeviceGetHandleByIndex(0)
                    gpu_util = float(pynvml.nvmlDeviceGetUtilizationRates(h).gpu)
                    vram_gb = float(pynvml.nvmlDeviceGetMemoryInfo(h).used / (1024 ** 3))
                except Exception:
                    pass

                self.bridge.notify_metrics(cpu, gpu_util, vram_gb, ram_gb)
            except Exception:
                pass

        threading.Thread(target=fetch, daemon=True).start()

    # ── Fullscreen & Drag Support ──────────────────────────────

    def toggle_fullscreen_mode(self):
        self.set_fullscreen(not self._is_fullscreen)

    def set_fullscreen(self, fullscreen: bool):
        self._is_fullscreen = fullscreen
        if fullscreen:
            self.showFullScreen()
        else:
            self.showNormal()
            self.resize(1020, 560)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self._is_fullscreen:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def paintEvent(self, event):
        """Draw ambient backdrop for entire HUD window."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Translucent sci-fi background frame
        bg_col = QColor(6, 12, 20, 225) if not self._is_fullscreen else QColor(4, 8, 14, 240)
        painter.setBrush(QBrush(bg_col))
        painter.setPen(QPen(QColor(0, 240, 255, 80), 1.2))
        painter.drawRoundedRect(QRectF(4, 4, self.width() - 8, self.height() - 8), 12, 12)
