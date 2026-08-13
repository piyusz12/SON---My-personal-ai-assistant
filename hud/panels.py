# hud/panels.py — Floating Holographic HUD Panels for SON V3
"""
Floating Glassmorphic HUD Panels:
- SystemHUDWidget (CPU, RTX 4060 GPU %, VRAM, RAM)
- PerceptionHUDWidget (Camera stream presence, enrolled face recognition card)
- ActionPipelineWidget (High-level thought execution step-by-step visualization)
- SubtitleBannerWidget (Movie-style glowing transcription banner)
"""
import time
import math
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QLinearGradient
)
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout


class GlassPanel(QWidget):
    """Base class for dark glassmorphism sci-fi panels."""
    def __init__(self, parent=None, width: int = 240, height: int = 150):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._glow_color = QColor(0, 240, 255, 180)
        self._bg_color = QColor(10, 15, 25, 200)

    def paint_glass_frame(self, painter: QPainter, title: str):
        painter.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        rect = QRectF(2, 2, w - 4, h - 4)

        # Background
        painter.setBrush(QBrush(self._bg_color))
        painter.setPen(QPen(QColor(0, 240, 255, 60), 1.0))
        painter.drawRoundedRect(rect, 8, 8)

        # Corner Tactical Accents (Iron Man HUD style)
        accent_pen = QPen(self._glow_color, 1.8)
        painter.setPen(accent_pen)
        # Top-Left
        painter.drawLine(2, 14, 2, 2)
        painter.drawLine(2, 2, 14, 2)
        # Top-Right
        painter.drawLine(w - 14, 2, w - 2, 2)
        painter.drawLine(w - 2, 2, w - 2, 14)
        # Bottom-Left
        painter.drawLine(2, h - 14, 2, h - 2)
        painter.drawLine(2, h - 2, 14, h - 2)
        # Bottom-Right
        painter.drawLine(w - 14, h - 2, w - 2, h - 2)
        painter.drawLine(w - 2, h - 14, w - 2, h - 2)

        # Title Banner
        painter.setFont(QFont("Consolas", 8, QFont.Bold))
        painter.setPen(QPen(self._glow_color, 1.0))
        painter.drawText(12, 18, title.upper())

        # Header underline
        painter.setPen(QPen(QColor(0, 240, 255, 40), 1.0))
        painter.drawLine(10, 24, w - 10, 24)


class SystemHUDWidget(GlassPanel):
    """Visualizes CPU, RTX 4060 GPU, VRAM, and RAM metrics."""
    def __init__(self, parent=None):
        super().__init__(parent, width=250, height=170)
        self._cpu = 15.0
        self._gpu = 4.0
        self._vram_gb = 4.8
        self._vram_total = 8.0
        self._ram_gb = 8.4
        self._ram_total = 16.0

    def update_metrics(self, cpu: float, gpu: float, vram_gb: float, ram_gb: float):
        self._cpu = cpu
        self._gpu = gpu
        self._vram_gb = vram_gb
        self._ram_gb = ram_gb
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        self.paint_glass_frame(painter, "System Diagnostics")

        metrics = [
            ("CPU UTIL", f"{self._cpu:.1f}%", self._cpu / 100.0),
            ("GPU (4060)", f"{self._gpu:.1f}%", self._gpu / 100.0),
            ("VRAM", f"{self._vram_gb:.1f}/{self._vram_total:.0f} GB", self._vram_gb / self._vram_total),
            ("RAM", f"{self._ram_gb:.1f}/{self._ram_total:.0f} GB", self._ram_gb / self._ram_total),
        ]

        y_start = 42
        row_h = 28
        bar_w = 90
        bar_h = 6

        for i, (label, val_str, ratio) in enumerate(metrics):
            y = y_start + i * row_h
            painter.setFont(QFont("Consolas", 8, QFont.Normal))
            painter.setPen(QPen(QColor(200, 230, 255, 220), 1.0))
            painter.drawText(12, y, label)

            # Value text
            painter.setFont(QFont("Consolas", 8, QFont.Bold))
            painter.drawText(self.width() - 85, y, val_str)

            # Progress Bar Background
            bar_x = self.width() - 175
            bar_y = y - 8
            painter.setBrush(QBrush(QColor(20, 35, 50, 180)))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 3, 3)

            # Filled Bar Gradient
            fill_w = max(4.0, min(bar_w, bar_w * ratio))
            grad = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
            if ratio > 0.85:
                grad.setColorAt(0.0, QColor(255, 170, 0, 230))
                grad.setColorAt(1.0, QColor(255, 50, 70, 255))
            else:
                grad.setColorAt(0.0, QColor(0, 180, 255, 200))
                grad.setColorAt(1.0, QColor(0, 255, 200, 255))

            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 3, 3)


class PerceptionHUDWidget(GlassPanel):
    """Visualizes Real-Time Camera Perception, Person Counting & Face Recognition."""
    def __init__(self, parent=None):
        super().__init__(parent, width=250, height=170)
        self._camera_active = True
        self._person_count = 0
        self._recognized_name = "None"
        self._confidence = 0.0

    def update_perception(self, active: bool, person_count: int, name: str | None = None, confidence: float = 0.0):
        self._camera_active = active
        self._person_count = person_count
        self._recognized_name = name or ("Unidentified" if person_count > 0 else "None")
        self._confidence = confidence
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        self.paint_glass_frame(painter, "Optical Perception")

        # Camera Status Indicator
        status_col = QColor(0, 255, 170, 240) if self._camera_active else QColor(255, 70, 70, 220)
        painter.setBrush(QBrush(status_col))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(18, 42), 4, 4)

        painter.setFont(QFont("Consolas", 8, QFont.Bold))
        painter.setPen(QPen(QColor(220, 240, 255, 230), 1.0))
        cam_text = "CAM: ONLINE" if self._camera_active else "CAM: PAUSED"
        painter.drawText(28, 46, cam_text)

        # Person Count Badge
        painter.setFont(QFont("Consolas", 8, QFont.Normal))
        painter.drawText(14, 75, f"OCCUPANCY: {self._person_count} PERSON(S)")

        # Target Recognition Box
        box_rect = QRectF(12, 88, self.width() - 24, 65)
        painter.setBrush(QBrush(QColor(15, 25, 40, 160)))
        painter.setPen(QPen(QColor(0, 240, 255, 80), 1.0))
        painter.drawRoundedRect(box_rect, 6, 6)

        # Face Icon / Reticle in Box
        painter.setPen(QPen(QColor(0, 240, 255, 180), 1.2))
        painter.drawEllipse(QPointF(32, 120), 12, 12)
        painter.drawArc(QRectF(20, 124, 24, 16), int(0 * 16), int(180 * 16))

        # Identity text
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        painter.setPen(QPen(QColor(255, 255, 255, 240), 1.0))
        painter.drawText(54, 112, f"ID: {self._recognized_name}")

        # Confidence Bar
        painter.setFont(QFont("Consolas", 7, QFont.Normal))
        painter.setPen(QPen(QColor(150, 200, 255, 200), 1.0))
        conf_str = f"CONF: {int(self._confidence * 100)}%" if self._confidence > 0 else "SCANNING..."
        painter.drawText(54, 128, conf_str)

        if self._confidence > 0:
            bar_w = 110
            bar_h = 4
            painter.setBrush(QBrush(QColor(30, 45, 60, 200)))
            painter.setPen(Qt.NoPen)
            painter.drawRect(QRectF(54, 134, bar_w, bar_h))

            fill_w = bar_w * min(1.0, self._confidence)
            painter.setBrush(QBrush(QColor(0, 255, 180, 230)))
            painter.drawRect(QRectF(54, 134, fill_w, bar_h))


class ActionPipelineWidget(GlassPanel):
    """Step-by-step visual thought execution graph (Intent ➔ Tool ➔ Run ➔ Done)."""
    def __init__(self, parent=None):
        super().__init__(parent, width=420, height=85)
        self._steps = ["INTENT", "TOOL SELECT", "EXECUTION", "VALIDATE", "COMPLETE"]
        self._active_step = 0  # 0 to 4
        self._action_desc = "Listening for prompt"

    def set_pipeline_stage(self, stage_idx: int, description: str):
        self._active_step = max(0, min(len(self._steps) - 1, stage_idx))
        self._action_desc = description
        self.update()

    def reset_pipeline(self):
        self._active_step = 0
        self._action_desc = "System Ready"
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        self.paint_glass_frame(painter, "Action Execution Pipeline")

        # Action Description Banner
        painter.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        painter.setPen(QPen(QColor(255, 220, 150, 240), 1.0))
        painter.drawText(14, 40, f"▶ {self._action_desc[:55]}")

        # Pipeline Flow Graph (Nodes + Connecting Lines)
        y_nodes = 62
        num_nodes = len(self._steps)
        spacing = (self.width() - 50) / (num_nodes - 1)

        # Draw Connecting Line
        line_pen = QPen(QColor(0, 240, 255, 60), 1.5)
        painter.setPen(line_pen)
        painter.drawLine(25, y_nodes, int(25 + (num_nodes - 1) * spacing), y_nodes)

        # Draw Nodes
        for i, step_name in enumerate(self._steps):
            x = int(25 + i * spacing)
            if i < self._active_step:
                # Completed node
                col = QColor(0, 255, 170, 250)
                painter.setBrush(QBrush(col))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPointF(x, y_nodes), 4, 4)
            elif i == self._active_step:
                # Active pulsing node
                col = QColor(255, 180, 0, 255)
                painter.setBrush(QBrush(col))
                painter.setPen(QPen(QColor(255, 255, 255, 200), 1.2))
                painter.drawEllipse(QPointF(x, y_nodes), 5.5, 5.5)
            else:
                # Future node
                col = QColor(40, 60, 80, 180)
                painter.setBrush(QBrush(col))
                painter.setPen(QPen(QColor(0, 240, 255, 40), 1.0))
                painter.drawEllipse(QPointF(x, y_nodes), 3, 3)

            # Node label
            painter.setFont(QFont("Consolas", 6, QFont.Normal))
            label_col = QColor(220, 240, 255, 220) if i <= self._active_step else QColor(100, 130, 160, 140)
            painter.setPen(QPen(label_col, 1.0))
            metrics = painter.fontMetrics()
            w = metrics.horizontalAdvance(step_name)
            painter.drawText(int(x - w / 2), y_nodes + 14, step_name)


class SubtitleBannerWidget(QWidget):
    """Movie-grade glowing dialogue subtitle bar."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._speaker = "SON"
        self._text = "I'm online and ready, Dad."
        self._alpha = 1.0

    def set_subtitle(self, speaker: str, text: str):
        self._speaker = speaker
        self._text = text
        self.update()

    def paintEvent(self, event):
        if not self._text:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()

        # Translucent Banner Background
        rect = QRectF(10, 4, w - 20, h - 8)
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QColor(5, 10, 20, 0))
        grad.setColorAt(0.2, QColor(5, 10, 20, 190))
        grad.setColorAt(0.8, QColor(5, 10, 20, 190))
        grad.setColorAt(1.0, QColor(5, 10, 20, 0))

        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 6, 6)

        # Speaker Tag
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        tag_color = QColor(0, 240, 255, 240) if self._speaker == "SON" else QColor(255, 180, 0, 240)
        painter.setPen(QPen(tag_color, 1.0))
        painter.drawText(24, 30, f"[{self._speaker}]:")

        # Subtitle Text
        painter.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        painter.setPen(QPen(QColor(255, 255, 255, 240), 1.0))
        painter.drawText(75, 30, self._text)
