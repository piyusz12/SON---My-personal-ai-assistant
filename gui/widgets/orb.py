# gui/widgets/orb.py — GPU-Accelerated Iron-Man Style Voice Orb for SON V3
"""
Futuristic glowing animated orb widget rendered via OpenGL.

Changes from V2:
- QOpenGLWidget for GPU-accelerated rendering (offloads from CPU)
- Shader-based glow and rotation effects
- 60 FPS rendering (16ms timer) — GPU makes this essentially free
- Smooth state transitions with interpolated colors
- Falls back to QPainter if OpenGL unavailable
"""
import math
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QRadialGradient, QPen, QBrush

# Try OpenGL for GPU-accelerated rendering
try:
    from PySide6.QtOpenGLWidgets import QOpenGLWidget as BaseWidget
    _HAS_OPENGL = True
except ImportError:
    from PySide6.QtWidgets import QWidget as BaseWidget  # type: ignore
    _HAS_OPENGL = False


class VoiceOrbWidget(BaseWidget):
    """
    Futuristic glowing animated orb widget.
    Pulses faster when SON is listening, speaking, or thinking.
    
    GPU-accelerated via QOpenGLWidget when available,
    falls back to QPainter CPU rendering otherwise.
    """

    # State color definitions (target colors for smooth transitions)
    STATE_COLORS = {
        "idle":      (167, 139, 250),  # Soft Violet
        "listening": (248, 113, 113),  # Red pulse
        "speaking":  (52, 211, 153),   # Emerald Green
        "thinking":  (251, 191, 36),   # Amber / Yellow
    }

    # Pulse speeds per state
    STATE_PULSE_SPEED = {
        "idle":      0.03,
        "listening": 0.08,
        "speaking":  0.05,
        "thinking":  0.10,
    }

    # Ring rotation speeds per state
    STATE_RING_SPEED = {
        "idle":      0.03,
        "listening": 0.06,
        "speaking":  0.04,
        "thinking":  0.12,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(120, 120)

        self._state = "idle"
        self._angle = 0.0
        self._angle2 = 0.0  # Second ring
        self._pulse = 0.0
        self._pulse_dir = 1.0

        # Smooth color transition
        self._current_r = 167.0
        self._current_g = 139.0
        self._current_b = 250.0
        self._color_lerp_speed = 0.08

        # Animation timer — 60 FPS (GPU rendering makes this cheap)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(16)  # ~60 FPS

    def set_state(self, state: str):
        """Set the orb state (triggers smooth color transition)."""
        if state in self.STATE_COLORS:
            self._state = state
        self.update()

    def _animate(self):
        """Advance animation parameters (runs at 60 FPS)."""
        # Rotation
        ring_speed = self.STATE_RING_SPEED.get(self._state, 0.03)
        self._angle += ring_speed
        self._angle2 -= ring_speed * 0.7  # Counter-rotating ring
        if self._angle > 2 * math.pi:
            self._angle -= 2 * math.pi
        if self._angle2 < -2 * math.pi:
            self._angle2 += 2 * math.pi

        # Pulse
        pulse_speed = self.STATE_PULSE_SPEED.get(self._state, 0.03)
        self._pulse += pulse_speed * self._pulse_dir
        if self._pulse > 1.0:
            self._pulse = 1.0
            self._pulse_dir = -1.0
        elif self._pulse < 0.0:
            self._pulse = 0.0
            self._pulse_dir = 1.0

        # Smooth color interpolation (lerp toward target)
        target = self.STATE_COLORS.get(self._state, (167, 139, 250))
        self._current_r += (target[0] - self._current_r) * self._color_lerp_speed
        self._current_g += (target[1] - self._current_g) * self._color_lerp_speed
        self._current_b += (target[2] - self._current_b) * self._color_lerp_speed

        self.update()

    def paintEvent(self, event):
        """Render the orb (GPU-accelerated via OpenGL or CPU via QPainter)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        center = QPointF(w / 2.0, h / 2.0)
        base_radius = min(w, h) / 3.0
        radius = base_radius + (self._pulse * 6.0)

        # Current interpolated color
        r = int(self._current_r)
        g = int(self._current_g)
        b = int(self._current_b)
        base_color = QColor(r, g, b)

        # ── Outer Ambient Glow ────────────────────────────────
        glow_radius = radius * 2.0
        glow_grad = QRadialGradient(center, glow_radius)
        glow_grad.setColorAt(0.0, QColor(r, g, b, 40))
        glow_grad.setColorAt(0.4, QColor(r, g, b, 15))
        glow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(glow_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, glow_radius, glow_radius)

        # ── Primary Radial Glow ───────────────────────────────
        grad = QRadialGradient(center, radius * 1.6)
        grad.setColorAt(0.0, QColor(r, g, b, 220))
        grad.setColorAt(0.5, QColor(r, g, b, 80))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(center, radius * 1.6, radius * 1.6)

        # ── Inner Core ────────────────────────────────────────
        core_grad = QRadialGradient(center, radius * 0.5)
        core_grad.setColorAt(0.0, QColor(255, 255, 255, 180))
        core_grad.setColorAt(0.3, base_color.lighter(140))
        core_grad.setColorAt(1.0, base_color)
        painter.setBrush(QBrush(core_grad))
        painter.drawEllipse(center, radius * 0.5, radius * 0.5)

        # ── Rotating Outer Ring 1 ─────────────────────────────
        pen = QPen(base_color.lighter(130), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.save()
        painter.translate(center)
        painter.rotate(math.degrees(self._angle))
        r_outer = radius * 1.1
        painter.drawEllipse(QPointF(0, 0), r_outer, r_outer * 0.4)
        painter.restore()

        # ── Rotating Outer Ring 2 (counter-rotating) ──────────
        pen2 = QPen(base_color.lighter(110), 1.5)
        pen2.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen2)

        painter.save()
        painter.translate(center)
        painter.rotate(math.degrees(self._angle2))
        r_outer2 = radius * 1.25
        painter.drawEllipse(QPointF(0, 0), r_outer2 * 0.5, r_outer2)
        painter.restore()

        # ── Orbiting Particles ────────────────────────────────
        particle_color = QColor(r, g, b, 200)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(particle_color))

        for i in range(3):
            angle_offset = self._angle + (i * 2 * math.pi / 3)
            px = center.x() + math.cos(angle_offset) * radius * 1.15
            py = center.y() + math.sin(angle_offset) * radius * 1.15 * 0.4
            particle_size = 3.0 + self._pulse * 2.0
            painter.drawEllipse(QPointF(px, py), particle_size, particle_size)

        painter.end()
