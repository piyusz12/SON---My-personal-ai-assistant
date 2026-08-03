# gui/widgets/status_bar.py — Status Bar & Service Badges Widget for SON V3
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt


class StatusBarWidget(QWidget):
    """
    Status bar displaying active mode, Ollama status, and Docker status badges.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)

        self.lbl_mode = QLabel("MODE: Desktop Assistant (V3)")
        self.lbl_mode.setStyleSheet("color: #a78bfa; font-weight: bold; font-size: 11px;")

        self.lbl_ollama = QLabel("● Ollama: Checking...")
        self.lbl_ollama.setStyleSheet("color: #fbbf24; font-size: 11px;")

        self.lbl_docker = QLabel("● Docker: Checking...")
        self.lbl_docker.setStyleSheet("color: #fbbf24; font-size: 11px;")

        layout.addWidget(self.lbl_mode)
        layout.addStretch()
        layout.addWidget(self.lbl_ollama)
        layout.addWidget(self.lbl_docker)

    def update_services(self, data: dict):
        if data.get("ollama_online"):
            model = data.get("ollama_model", "Online")
            self.lbl_ollama.setText(f"● Ollama: {model}")
            self.lbl_ollama.setStyleSheet("color: #34d399; font-weight: bold; font-size: 11px;")
        else:
            self.lbl_ollama.setText("● Ollama: Offline")
            self.lbl_ollama.setStyleSheet("color: #f87171; font-weight: bold; font-size: 11px;")

        if data.get("docker_online"):
            self.lbl_docker.setText("● Docker: Online")
            self.lbl_docker.setStyleSheet("color: #34d399; font-weight: bold; font-size: 11px;")
        else:
            self.lbl_docker.setText("● Docker: Offline")
            self.lbl_docker.setStyleSheet("color: #f87171; font-weight: bold; font-size: 11px;")
