from __future__ import annotations

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from shortube.desktop.workers import run_in_thread


class AnalyticsPage(QWidget):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        row = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh Analytics")
        self.refresh_btn.setObjectName("primary")
        self.refresh_btn.clicked.connect(self._refresh)
        row.addWidget(self.refresh_btn)
        self.hint = QLabel(
            "Shows stats for uploaded videos. Requires a connected YouTube account."
        )
        self.hint.setStyleSheet("color: #8b93a3;")
        row.addWidget(self.hint, 1)
        root.addLayout(row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Topic", "Views", "Likes", "Comments", "Published"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 480)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        root.addWidget(self.table, 1)

    def _refresh(self) -> None:
        from shortube.analytics import refresh_all_analytics

        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Refreshing...")

        def work() -> list[dict]:
            return refresh_all_analytics()

        def done(rows: list[dict]) -> None:
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText("Refresh Analytics")
            self.table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                self.table.setItem(i, 0, QTableWidgetItem(r.get("topic_title") or ""))
                self.table.setItem(i, 1, QTableWidgetItem(str(r.get("views", 0))))
                self.table.setItem(i, 2, QTableWidgetItem(str(r.get("likes", 0))))
                self.table.setItem(i, 3, QTableWidgetItem(str(r.get("comments", 0))))
                published = str(r.get("published_at") or "")[:16].replace("T", " ")
                self.table.setItem(i, 4, QTableWidgetItem(published))
            self.table.resizeRowsToContents()
            self.window.notify(f"Analytics for {len(rows)} videos")

        def failed(error: str) -> None:
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText("Refresh Analytics")
            self.window.notify(f"Analytics failed: {error[:120]}", 8000)

        run_in_thread(work, done, failed)
