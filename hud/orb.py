# hud/orb.py — Central Interactive Holographic AI Core Orb
"""
High-Performance Holographic Orb Widget for SON V3.
Rendered via QPainter with GPU-accelerated composition, antialiasing,
and mathematical particle/ring physics running at 60 FPS.
"""
import math
import random
import numpy as np
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient,
    QLinearGradient, QFont, QPainterPath
)
from PySide6.QtWidgets import QWidget

from hud.state import HUDState, STATE_CONFIGS, StateVisualConfig


class Particle:
    """A floating stardust particle orbiting the core."""
    def __init__(self, cx: float, cy: float, min_r: float, max_r: float):
        self.angle = random.uniform(0, 2 * math.pi)
        self.dist = random.uniform(min_r, max_r)
        self.base_dist = self.dist
        self.size = random.uniform(1.5, 3.5)
        self.speed = random.uniform(0.008, 0.025) * (1 if random.random() > 0.5 else -1)
        self.alpha = random.uniform(0.3, 0.9)
        self.twinkle_speed = random.uniform(0.02, 0.06)
        self.phase = random.uniform(0, math.pi * 2)

    def update(self, speed_mult: float):
        self.angle += self.speed * speed_mult
        self.phase += self.twinkle_speed
        # Subtle radial oscillation
        self.dist = self.base_dist + math.sin(self.phase) * 6.0


class HolographicOrbWidget(QWidget):
    """
    Central Holographic AI Core.
    Features:
    - Gyroscopic multi-tier rotating reticles
    - Outer orbital particle field
    - Audio-reactive pulsing plasma core
    - Dynamic state morphing (Cyan ➔ Purple ➔ Amber ➔ Red)
    """

    def __init__(self, parent=None, size: int = 340):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._state = HUDState.IDLE
        self._cfg = STATE_CONFIGS[self._state]

        # Physics & Animation State
        self._angle_ring1 = 0.0
        self._angle_ring2 = 0.0
        self._angle_ring3 = 0.0
        self._pulse_phase = 0.0
        self._audio_level = 0.0  # 0.0 to 1.0 (from mic or TTS)
        self._target_audio_level = 0.0
        self._activity_text = "READY"

        # Initialize Orbiting Particles
        cx, cy = size / 2, size / 2
        self._particles = [
            Particle(cx, cy, size * 0.28, size * 0.46)
            for _ in range(60)
        ]

        # Pre-calculated waveform samples
        self._wave_history = [0.0] * 32

    def set_state(self, state: HUDState, activity_text: str | None = None):
        """Set visual state of the holographic orb."""
        self._state = state
        self._cfg = STATE_CONFIGS.get(state, STATE_CONFIGS[HUDState.IDLE])
        if activity_text:
            self._activity_text = activity_text
        else:
            self._activity_text = self._cfg.status_label
        self.update()

    def set_audio_level(self, level: float):
        """Update live audio energy (0.0 to 1.0) for reactive pulsing."""
        self._target_audio_level = max(0.0, min(1.0, level))

    def set_activity_text(self, text: str):
        """Update the center/bottom activity text."""
        self._activity_text = text
        self.update()

    def tick(self):
        """Called every frame (~60 FPS) to advance physics and trigger paint."""
        speed = self._cfg.ring_speed
        self._angle_ring1 = (self._angle_ring1 + speed * 1.0) % 360
        self._angle_ring2 = (self._angle_ring2 - speed * 1.4) % 360
        self._angle_ring3 = (self._angle_ring3 + speed * 0.7) % 360
        self._pulse_phase = (self._pulse_phase + self._cfg.pulse_speed) % (2 * math.pi)

        # Smooth audio level transition
        self._audio_level += (self._target_audio_level - self._audio_level) * 0.35

        # Update Particles
        for p in self._particles:
            p.update(self._cfg.particle_speed)

        # Rotate wave history
        self._wave_history.pop(0)
        self._wave_history.append(self._audio_level * self._cfg.wave_amplitude)

        self.update()

    # ── Paint Event ───────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        cx = self.width() / 2
        cy = self.height() / 2
        base_radius = self.width() * 0.38

        # 1. Draw Outer Particle Field
        self._draw_particles(painter, cx, cy)

        # 2. Draw Outer Glowing Ambient Halo
        self._draw_ambient_glow(painter, cx, cy, base_radius)

        # 3. Draw Concentric Gyroscopic Rings
        self._draw_gyro_rings(painter, cx, cy, base_radius)

        # 4. Draw Audio Reactive Waveform Circle
        self._draw_audio_waveform(painter, cx, cy, base_radius * 0.65)

        # 5. Draw Core Pulsing Holographic Sphere
        self._draw_core_sphere(painter, cx, cy, base_radius * 0.48)

        # 6. Draw Reticle Centerpiece & Status Text
        self._draw_centerpiece(painter, cx, cy)

    # ── Rendering Layers ──────────────────────────────────────

    def _draw_ambient_glow(self, painter: QPainter, cx: float, cy: float, radius: float):
        pulse = math.sin(self._pulse_phase) * 0.15 + (self._audio_level * 0.25)
        glow_r = radius * (1.1 + pulse)
        glow_grad = QRadialGradient(cx, cy, glow_r)
        glow_grad.setColorAt(0.0, self._cfg.glow_color)
        glow_grad.setColorAt(0.6, QColor(self._cfg.glow_color.red(), self._cfg.glow_color.green(), self._cfg.glow_color.blue(), 15))
        glow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setBrush(QBrush(glow_grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

    def _draw_particles(self, painter: QPainter, cx: float, cy: float):
        count = min(self._cfg.particle_count, len(self._particles))
        primary = self._cfg.primary_color

        for i in range(count):
            p = self._particles[i]
            px = cx + math.cos(p.angle) * p.dist
            py = cy + math.sin(p.angle) * p.dist
            alpha = int(255 * p.alpha * (0.6 + 0.4 * math.sin(p.phase)))
            col = QColor(primary.red(), primary.green(), primary.blue(), max(10, min(255, alpha)))

            painter.setBrush(QBrush(col))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(px, py), p.size, p.size)

    def _draw_gyro_rings(self, painter: QPainter, cx: float, cy: float, radius: float):
        primary = self._cfg.primary_color
        secondary = self._cfg.secondary_color
        accent = self._cfg.accent_color

        # ── Ring 1: Outer Segmented Hex Arc (Clockwise)
        r1 = radius * 0.95
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._angle_ring1)

        pen1 = QPen(primary, 2.0, Qt.SolidLine)
        painter.setPen(pen1)
        painter.setBrush(Qt.NoBrush)

        # Draw 4 arcs with gaps
        for arc_idx in range(4):
            start_deg = arc_idx * 90 + 10
            span_deg = 65
            painter.drawArc(QRectF(-r1, -r1, r1 * 2, r1 * 2), int(start_deg * 16), int(span_deg * 16))

        # Tick marks on ring 1
        pen_tick = QPen(accent, 1.5)
        painter.setPen(pen_tick)
        for i in range(12):
            rad = math.radians(i * 30)
            x1 = math.cos(rad) * (r1 - 4)
            y1 = math.sin(rad) * (r1 - 4)
            x2 = math.cos(rad) * (r1 + 4)
            y2 = math.sin(rad) * (r1 + 4)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        painter.restore()

        # ── Ring 2: Middle Counter-Rotating Dashed Reticle
        r2 = radius * 0.80
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._angle_ring2)

        pen2 = QPen(secondary, 1.5, Qt.DashLine)
        pen2.setDashPattern([6, 8, 2, 8])
        painter.setPen(pen2)
        painter.drawEllipse(QPointF(0, 0), r2, r2)

        # 3 Crosshair Nodes
        painter.setBrush(QBrush(accent))
        painter.setPen(Qt.NoPen)
        for node_idx in range(3):
            n_rad = math.radians(node_idx * 120)
            nx = math.cos(n_rad) * r2
            ny = math.sin(n_rad) * r2
            painter.drawEllipse(QPointF(nx, ny), 3, 3)

        painter.restore()

        # ── Ring 3: Inner Orbital Arc
        r3 = radius * 0.64
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._angle_ring3)

        pen3 = QPen(primary, 1.2)
        painter.setPen(pen3)
        painter.drawArc(QRectF(-r3, -r3, r3 * 2, r3 * 2), int(45 * 16), int(90 * 16))
        painter.drawArc(QRectF(-r3, -r3, r3 * 2, r3 * 2), int(225 * 16), int(90 * 16))
        painter.restore()

    def _draw_audio_waveform(self, painter: QPainter, cx: float, cy: float, radius: float):
        """Draw circular audio spectrum bars around the core."""
        num_bars = len(self._wave_history)
        primary = self._cfg.primary_color
        accent = self._cfg.accent_color

        for i, val in enumerate(self._wave_history):
            angle = (i / num_bars) * 2 * math.pi
            pulse = math.sin(self._pulse_phase * 2 + i) * 0.1
            bar_len = 3.0 + (val * 24.0) + (pulse * 4.0)

            x1 = cx + math.cos(angle) * radius
            y1 = cy + math.sin(angle) * radius
            x2 = cx + math.cos(angle) * (radius + bar_len)
            y2 = cy + math.sin(angle) * (radius + bar_len)

            alpha = int(120 + min(135, val * 350))
            col = QColor(accent.red(), accent.green(), accent.blue(), alpha) if val > 0.4 else QColor(primary.red(), primary.green(), primary.blue(), alpha)

            pen = QPen(col, 2.0, Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _draw_core_sphere(self, painter: QPainter, cx: float, cy: float, radius: float):
        """Draw pulsing central holographic plasma sphere."""
        pulse = math.sin(self._pulse_phase) * 0.08 + (self._audio_level * 0.20)
        curr_r = radius * (1.0 + pulse)

        grad = QRadialGradient(cx, cy, curr_r)
        pri = self._cfg.primary_color
        sec = self._cfg.secondary_color
        acc = self._cfg.accent_color

        grad.setColorAt(0.0, QColor(acc.red(), acc.green(), acc.blue(), 230))
        grad.setColorAt(0.4, QColor(pri.red(), pri.green(), pri.blue(), 180))
        grad.setColorAt(0.8, QColor(sec.red(), sec.green(), sec.blue(), 80))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), curr_r, curr_r)

    def _draw_centerpiece(self, painter: QPainter, cx: float, cy: float):
        """Draw SON Core Logo & live state badge."""
        painter.setPen(QPen(self._cfg.accent_color, 1.5))
        painter.setFont(QFont("Consolas", 10, QFont.Bold))

        # Central ◉ SON AI CORE
        text = "SON"
        metrics = painter.fontMetrics()
        w = metrics.horizontalAdvance(text)
        painter.drawText(int(cx - w / 2), int(cy - 2), text)

        # Subtle sub-label
        painter.setFont(QFont("Consolas", 7, QFont.Normal))
        painter.setPen(QPen(self._cfg.primary_color, 1.0))
        sub = "AI CORE"
        w_sub = painter.fontMetrics().horizontalAdvance(sub)
        painter.drawText(int(cx - w_sub / 2), int(cy + 12), sub)

        # Bottom status pill
        painter.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        status_text = self._activity_text.upper()
        w_st = painter.fontMetrics().horizontalAdvance(status_text) + 16
        pill_rect = QRectF(cx - w_st / 2, self.height() - 26, w_st, 18)

        # Pill background
        pill_bg = QColor(10, 20, 30, 190)
        painter.setBrush(QBrush(pill_bg))
        painter.setPen(QPen(self._cfg.primary_color, 1.0))
        painter.drawRoundedRect(pill_rect, 9, 9)

        # Pill text
        painter.setPen(QPen(self._cfg.accent_color, 1.0))
        painter.drawText(pill_rect, Qt.AlignCenter, status_text)
