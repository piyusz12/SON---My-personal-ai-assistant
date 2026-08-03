# gui/widgets/system_monitor.py — System Monitor Widget for SON V3
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QGroupBox
from PySide6.QtCore import Qt


class SystemMonitorWidget(QWidget):
    """
    Displays live CPU, GPU (RTX 4060), VRAM, RAM, and Temperature metrics.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        group = QGroupBox("HARDWARE TELEMETRY")
        group.setStyleSheet("""
            QGroupBox {
                color: #a78bfa;
                font-weight: bold;
                border: 1px solid #374151;
                border-radius: 8px;
                margin-top: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        g_layout = QVBoxLayout(group)

        # CPU Progress
        self.lbl_cpu = QLabel("CPU: 0%")
        self.lbl_cpu.setStyleSheet("color: #e5e7eb; font-size: 11px;")
        self.pb_cpu = QProgressBar()
        self.pb_cpu.setStyleSheet(self._bar_style("#60a5fa"))
        g_layout.addWidget(self.lbl_cpu)
        g_layout.addWidget(self.pb_cpu)

        # RAM Progress
        self.lbl_ram = QLabel("RAM: 0 / 0 GB (0%)")
        self.lbl_ram.setStyleSheet("color: #e5e7eb; font-size: 11px;")
        self.pb_ram = QProgressBar()
        self.pb_ram.setStyleSheet(self._bar_style("#a78bfa"))
        g_layout.addWidget(self.lbl_ram)
        g_layout.addWidget(self.pb_ram)

        # GPU Progress (NVIDIA RTX 4060)
        self.lbl_gpu = QLabel("GPU (RTX 4060): 0% | 0 MB VRAM")
        self.lbl_gpu.setStyleSheet("color: #e5e7eb; font-size: 11px;")
        self.pb_gpu = QProgressBar()
        self.pb_gpu.setStyleSheet(self._bar_style("#34d399"))
        g_layout.addWidget(self.lbl_gpu)
        g_layout.addWidget(self.pb_gpu)

        layout.addWidget(group)

    @staticmethod
    def _bar_style(color: str) -> str:
        return f"""
            QProgressBar {{
                border: 1px solid #1f2937;
                border-radius: 4px;
                background-color: #111827;
                height: 10px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """

    def update_metrics(self, data: dict):
        cpu = int(data.get("cpu_percent", 0))
        self.lbl_cpu.setText(f"CPU: {cpu}%")
        self.pb_cpu.setValue(cpu)

        ram_pct = int(data.get("ram_percent", 0))
        r_used = data.get("ram_used_gb", 0)
        r_tot = data.get("ram_total_gb", 0)
        self.lbl_ram.setText(f"RAM: {r_used:.1f} / {r_tot:.1f} GB ({ram_pct}%)")
        self.pb_ram.setValue(ram_pct)

        gpu_util = int(data.get("gpu_util", 0))
        v_used = data.get("gpu_vram_used_mb", 0)
        v_tot = data.get("gpu_vram_total_mb", 8188)
        v_pct = int((v_used / v_tot) * 100) if v_tot > 0 else 0
        temp = data.get("gpu_temp_c", 0)
        self.lbl_gpu.setText(f"GPU (RTX 4060): {gpu_util}% | {v_used:.0f}/{v_tot:.0f} MB ({temp:.0f}°C)")
        self.pb_gpu.setValue(v_pct)
