from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser, QLineEdit, QPushButton
from PySide6.QtCore import Signal


class ChatViewWidget(QWidget):
    """
    Rich conversation view supporting text prompts and markdown responses.
    """
    send_prompt = Signal(str)
    voice_toggled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Markdown Chat Output
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setStyleSheet("""
            QTextBrowser {
                background-color: #111827;
                color: #f3f4f6;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }
        """)
        layout.addWidget(self.browser)

        # Input Row
        input_layout = QHBoxLayout()

        self.txt_input = QLineEdit()
        self.txt_input.setPlaceholderText("Ask SON anything or type a command...")
        self.txt_input.setStyleSheet("""
            QLineEdit {
                background-color: #1f2937;
                color: #ffffff;
                border: 1px solid #4b5563;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #a78bfa;
            }
        """)
        self.txt_input.returnPressed.connect(self._on_send)

        self.btn_send = QPushButton("Send")
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #6d28d9;
            }
        """)
        self.btn_send.clicked.connect(self._on_send)

        self.btn_voice = QPushButton("🎤 Mic")
        self.btn_voice.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        self.btn_voice.clicked.connect(self.voice_toggled.emit)

        input_layout.addWidget(self.txt_input)
        input_layout.addWidget(self.btn_send)
        input_layout.addWidget(self.btn_voice)
        layout.addLayout(input_layout)

    def _on_send(self):
        text = self.txt_input.text().strip()
        if text:
            self.append_message("You", text, color="#60a5fa")
            self.txt_input.clear()
            self.send_prompt.emit(text)

    def append_message(self, sender: str, text: str, color: str = "#a78bfa"):
        formatted = f"""
        <div style='margin-bottom: 12px;'>
            <b style='color: {color}; font-size: 14px;'>{sender}</b><br>
            <span style='color: #e5e7eb;'>{text.replace("\n", "<br>")}</span>
        </div>
        """
        self.browser.append(formatted)
