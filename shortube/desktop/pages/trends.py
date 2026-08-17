from __future__ import annotations

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from shortube.config import get_settings
from shortube.db import Database
from shortube.desktop.workers import run_in_thread


class TrendsPage(QWidget):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        self.db = Database()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        row = QHBoxLayout()
        self.niche_input = QLineEdit(get_settings().niche)
        self.niche_input.setMaximumWidth(240)
        self.niche_input.setPlaceholderText("Niche")
        row.addWidget(self.niche_input)
        self.refresh_btn = QPushButton("Refresh Trends")
        self.refresh_btn.setObjectName("primary")
        self.refresh_btn.clicked.connect(self._refresh)
        row.addWidget(self.refresh_btn)
        self.generate_btn = QPushButton("Generate Selected")
        self.generate_btn.clicked.connect(self._generate_selected)
        row.addWidget(self.generate_btn)
        row.addStretch(1)
        root.addLayout(row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["#", "Title", "Source", "Score", "Used"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(1, 560)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 70)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self._generate_selected)
        root.addWidget(self.table, 1)

    def _refresh(self) -> None:
        from shortube.discover import discover

        niche = self.niche_input.text().strip() or get_settings().niche
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Fetching...")
        self.window.notify("Fetching trends...")

        def work() -> list[dict]:
            db = Database()
            ideas = discover(niche, max_results=10)
            for idea in ideas:
                db.add_topic(
                    idea.title, niche=niche,
                    source=idea.source, score=idea.score,
                )
            return [
                {"title": i.title, "source": i.source, "score": i.score}
                for i in ideas
            ]

        def done(ideas: list[dict]) -> None:
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText("Refresh Trends")
            self._populate(ideas)
            self.window.notify(f"{len(ideas)} trending topics found")

        def failed(error: str) -> None:
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText("Refresh Trends")
            self.window.notify(f"Trend refresh failed: {error[:120]}", 8000)

        run_in_thread(work, done, failed)

    def _populate(self, ideas: list[dict]) -> None:
        self.table.setRowCount(len(ideas))
        for i, idea in enumerate(ideas):
            used = "yes" if self.db.is_topic_used(idea["title"]) else ""
            items = [
                QTableWidgetItem(str(i + 1)),
                QTableWidgetItem(idea["title"]),
                QTableWidgetItem(idea.get("source") or ""),
                QTableWidgetItem(f"{idea.get('score', 0):.1f}"),
                QTableWidgetItem(used),
            ]
            for col, item in enumerate(items):
                self.table.setItem(i, col, item)
        self.table.resizeRowsToContents()

    def _generate_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            self.window.notify("Select a topic first")
            return
        topic = self.table.item(row, 1).text()
        self.window.queue_generate(topic, self.niche_input.text(), "private")
        self.window.navigate("dashboard")
