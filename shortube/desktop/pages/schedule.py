from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from shortube.scheduler import get_schedule_config, update_schedule_config


class SchedulePage(QWidget):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        group = QGroupBox("Automatic generation")
        form = QFormLayout(group)
        self.enabled = QCheckBox("Enable automatic generation")
        form.addRow("", self.enabled)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 168)
        self.interval_spin.setSuffix(" hours")
        form.addRow("Interval", self.interval_spin)
        self.max_daily_spin = QSpinBox()
        self.max_daily_spin.setRange(1, 100)
        self.max_daily_spin.setSuffix(" videos")
        form.addRow("Daily limit", self.max_daily_spin)
        self.niche_input = QLineEdit()
        self.niche_input.setPlaceholderText("Blank = default niche")
        form.addRow("Niche", self.niche_input)
        self.privacy_combo = QComboBox()
        self.privacy_combo.addItems(["private", "unlisted", "public"])
        form.addRow("Privacy", self.privacy_combo)
        root.addWidget(group)

        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        root.addWidget(status_group)

        save_row = QHBoxLayout()
        save_row.addStretch(1)
        self.save_btn = QPushButton("Save Schedule")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        save_row.addWidget(self.save_btn)
        root.addLayout(save_row)
        root.addStretch(1)

        self._refresh()

    def _refresh(self) -> None:
        cfg = get_schedule_config()
        self.enabled.setChecked(bool(cfg.get("enabled")))
        self.interval_spin.setValue(int(cfg.get("interval_hours", 6)))
        self.max_daily_spin.setValue(int(cfg.get("max_daily", 4)))
        self.niche_input.setText(str(cfg.get("niche") or ""))
        self.privacy_combo.setCurrentText(str(cfg.get("privacy") or "public"))
        running = bool(cfg.get("running"))
        state = "Running" if running else "Stopped"
        self.status_label.setText(
            f"Scheduler: {state} — "
            f"{cfg.get('generated_today', 0)}/{cfg.get('max_daily', 4)} "
            f"videos generated today"
        )

    def _save(self) -> None:
        payload = {
            "enabled": self.enabled.isChecked(),
            "interval_hours": self.interval_spin.value(),
            "max_daily": self.max_daily_spin.value(),
            "niche": self.niche_input.text().strip(),
            "privacy": self.privacy_combo.currentText(),
        }
        try:
            update_schedule_config(payload)
            self._refresh()
            self.window.refresh_scheduler_label()
            self.window.notify("Schedule saved")
        except (OSError, ValueError) as e:
            self.window.notify(f"Failed to save schedule: {e}", 8000)
