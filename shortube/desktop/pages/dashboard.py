from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from shortube.config import get_settings
from shortube.db import Database


def _card(title: str) -> tuple[QWidget, QVBoxLayout]:
    card = QWidget()
    card.setStyleSheet(
        "background-color: #1a1e26; border-radius: 12px; border: 1px solid #2a2f3a;"
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(20, 18, 20, 18)
    label = QLabel(title)
    label.setStyleSheet("font-size: 16px; font-weight: 700;")
    layout.addWidget(label)
    return card, layout


class DashboardPage(QWidget):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        self.db = Database()
        cfg = get_settings()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        gen_card, gen_layout = _card("Create a Short")
        row = QHBoxLayout()
        self.topic_input = QLineEdit()
        self.topic_input.setPlaceholderText("Topic — e.g. Mind-blowing facts about the universe")
        self.topic_input.returnPressed.connect(self._on_generate)
        row.addWidget(self.topic_input, 1)
        self.niche_input = QLineEdit(cfg.niche)
        self.niche_input.setMaximumWidth(180)
        self.niche_input.setPlaceholderText("Niche")
        row.addWidget(self.niche_input)
        self.privacy_combo = QComboBox()
        self.privacy_combo.addItems(["private", "unlisted", "public"])
        self.privacy_combo.setMaximumWidth(120)
        row.addWidget(self.privacy_combo)
        self.generate_btn = QPushButton("Generate")
        self.generate_btn.setObjectName("primary")
        self.generate_btn.clicked.connect(self._on_generate)
        row.addWidget(self.generate_btn)
        self.auto_btn = QPushButton("Auto")
        self.auto_btn.clicked.connect(self._on_auto)
        row.addWidget(self.auto_btn)
        gen_layout.addLayout(row)
        root.addWidget(gen_card)

        progress_card, progress_layout = _card("Job Progress")
        self.job_label = QLabel("No active job")
        self.job_label.setStyleSheet("font-weight: 600;")
        progress_layout.addWidget(self.job_label)
        self.stage_label = QLabel("")
        self.stage_label.setStyleSheet("color: #8b93a3;")
        progress_layout.addWidget(self.stage_label)
        bar_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        bar_row.addWidget(self.progress_bar, 1)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("danger")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        bar_row.addWidget(self.cancel_btn)
        progress_layout.addLayout(bar_row)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(180)
        progress_layout.addWidget(self.log_view)
        root.addWidget(progress_card)

        recent_card, recent_layout = _card("Recent Activity")
        self.recent_table = QTableWidget(0, 4)
        self.recent_table.setHorizontalHeaderLabels(
            ["Topic", "Status", "YouTube", "Created"]
        )
        self.recent_table.horizontalHeader().setStretchLastSection(True)
        self.recent_table.setColumnWidth(0, 380)
        self.recent_table.setColumnWidth(1, 110)
        self.recent_table.setColumnWidth(2, 260)
        self.recent_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.recent_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        recent_layout.addWidget(self.recent_table)
        root.addWidget(recent_card, 1)

        self.window.jobs.jobStarted.connect(self._on_started)
        self.window.jobs.jobProgress.connect(self._on_progress)
        self.window.jobs.jobFinished.connect(self._on_finished)
        self.window.jobs.jobFailed.connect(self._on_failed)
        self.window.jobs.jobCancelled.connect(self._on_cancelled)

        self._refresh_recent()

    def _on_generate(self) -> None:
        self.window.queue_generate(
            self.topic_input.text(),
            self.niche_input.text(),
            self.privacy_combo.currentText(),
        )

    def _on_auto(self) -> None:
        self.window.queue_auto(
            self.niche_input.text(),
            self.privacy_combo.currentText(),
        )

    def _on_cancel(self) -> None:
        self.window.jobs.cancel_current()
        self.log_view.appendPlainText("Cancelling job...")

    def _on_started(self, job_id: int, topic: str) -> None:
        self.job_label.setText(f"Running: {topic[:60]}")
        self.stage_label.setText("Starting...")
        self.progress_bar.setValue(0)
        self.cancel_btn.setEnabled(True)
        self.log_view.clear()

    def _on_progress(self, job_id: int, msg: str, pct: int) -> None:
        self.stage_label.setText(msg)
        self.log_view.appendPlainText(msg)
        if pct > 0:
            self.progress_bar.setValue(pct)

    def _reset_job_ui(self, message: str) -> None:
        self.job_label.setText(message)
        self.stage_label.setText("")
        self.cancel_btn.setEnabled(False)
        self._refresh_recent()

    def _on_finished(self, job_id: int, result: dict) -> None:
        url = result.get("url", "")
        self.log_view.appendPlainText(
            f"Done — {url}" if url else "Pipeline complete."
        )
        self.progress_bar.setValue(100)
        self._reset_job_ui("Job finished")
        self.window.notify("Video finished!" if url else "Pipeline complete")

    def _on_failed(self, job_id: int, error: str) -> None:
        self.log_view.appendPlainText(f"Failed: {error}")
        self._reset_job_ui("Job failed")
        self.window.notify(f"Job failed: {error[:120]}", 8000)

    def _on_cancelled(self, job_id: int) -> None:
        self.log_view.appendPlainText("Job cancelled")
        self._reset_job_ui("Job cancelled")
        self.window.notify("Job cancelled")

    def _refresh_recent(self) -> None:
        videos = self.db.get_recent_videos(limit=20)
        self.recent_table.setRowCount(len(videos))
        for i, v in enumerate(videos):
            topic_item = QTableWidgetItem(v.topic_title or "")
            topic_item.setToolTip(v.topic_title or "")
            status_item = QTableWidgetItem(v.status or "")
            url_item = QTableWidgetItem(v.youtube_url or "")
            created_item = QTableWidgetItem((v.created_at or "")[:19])
            self.recent_table.setItem(i, 0, topic_item)
            self.recent_table.setItem(i, 1, status_item)
            self.recent_table.setItem(i, 2, url_item)
            self.recent_table.setItem(i, 3, created_item)
        self.recent_table.resizeRowsToContents()
