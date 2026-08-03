# gui/widgets/orb.py — Animated Iron-Man Style Voice Orb for SON V3
import math
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QRadialGradient, QPen, QBrush


class VoiceOrbWidget(QWidget):
    """
    Futuristic glowing animated orb widget.
    Pulses faster when SON is listening, speaking, or thinking.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(120, 120)

        self._state = "idle"  # idle, listening, speaking, thinking
        self._angle = 0.0
        self._pulse = 0.0
        self._pulse_dir = 0.05

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(30)  # ~33 FPS

    def set_state(self, state: str):
        self._state = state
        self.update()

    def _animate(self):
        self._angle += 0.05
        if self._angle > 2 * math.pi:
            self._angle = 0.0

        self._pulse += self._pulse_dir
        if self._pulse > 1.0:
            self._pulse = 1.0
            self._pulse_dir = -0.05
        elif self._pulse < 0.0:
            self._pulse = 0.0
            self._pulse_dir = 0.05

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        center = QPointF(w / 2.0, h / 2.0)
        radius = min(w, h) / 3.0 + (self._pulse * 4.0)

        # Color mapping based on status
        if self._state == "listening":
            base_color = QColor(248, 113, 113)  # Red pulse
        elif self._state == "speaking":
            base_color = QColor(52, 211, 153)   # Emerald Green
        elif self._state == "thinking":
            base_color = QColor(251, 191, 36)   # Amber / Yellow
        else:
            base_color = QColor(167, 139, 250)  # Soft Violet

        # Radial Glow
        grad = QRadialGradient(center, radius * 1.6)
        grad.setColorAt(0.0, QColor(base_color.red(), base_color.green(), base_color.blue(), 220))
        grad.setColorAt(0.5, QColor(base_color.red(), base_color.green(), base_color.blue(), 80))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, radius * 1.6, radius * 1.6)

        # Inner Core
        painter.setBrush(QBrush(base_color))
        painter.drawEllipse(center, radius * 0.5, radius * 0.5)

        # Rotating Outer Rings
        pen = QPen(base_color.lighter(130), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoPen)

        r_outer = radius * 1.1
        dx = math.cos(self._angle) * r_outer
        dy = math.sin(self._angle) * r_outer
        painter.drawEllipse(center, r_outer, r_outer * 0.4)
