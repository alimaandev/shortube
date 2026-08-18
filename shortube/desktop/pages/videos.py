from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from shortube.db import Database

STATUS_COLORS = {
    "uploaded": "#4caf50",
    "assembled": "#4caf50",
    "done": "#4caf50",
    "failed": "#ef5350",
    "cancelled": "#ff9800",
    "pending": "#2196f3",
}


class VideosPage(QWidget):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        self.db = Database()
        self._videos: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        row = QHBoxLayout()
        self.open_btn = QPushButton("Open File")
        self.open_btn.clicked.connect(self._open_file)
        row.addWidget(self.open_btn)
        self.yt_btn = QPushButton("Open YouTube")
        self.yt_btn.clicked.connect(self._open_youtube)
        row.addWidget(self.yt_btn)
        self.retry_btn = QPushButton("Retry")
        self.retry_btn.clicked.connect(self._retry)
        row.addWidget(self.retry_btn)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh)
        row.addWidget(self.refresh_btn)
        row.addStretch(1)
        root.addLayout(row)

        body = QHBoxLayout()
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Topic", "Status", "Privacy", "Created", "Link"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 360)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 150)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._update_preview)
        body.addWidget(self.table, 1)

        right = QVBoxLayout()
        self.preview_label = QLabel("Select a video to preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(270, 480)
        self.preview_label.setMaximumWidth(300)
        self.preview_label.setStyleSheet(
            "background-color: #141821; border-radius: 12px;"
            "border: 1px solid #2a2f3a; color: #8b93a3;"
        )
        right.addWidget(self.preview_label)
        body.addLayout(right)
        root.addLayout(body, 1)

        self._refresh()

    def _refresh(self) -> None:
        self._videos = self.db.get_recent_videos(limit=50)
        self.table.setRowCount(len(self._videos))
        for i, v in enumerate(self._videos):
            topic_item = QTableWidgetItem(v.get("topic_title") or "")
            topic_item.setToolTip(v.get("topic_title") or "")
            status_item = QTableWidgetItem(v.get("status") or "")
            status_item.setForeground(
                Qt.GlobalColor.white
            )
            privacy_item = QTableWidgetItem(v.get("privacy") or "")
            created_item = QTableWidgetItem((v.get("created_at") or "")[:19])
            link_item = QTableWidgetItem(v.get("youtube_url") or "")
            self.table.setItem(i, 0, topic_item)
            self.table.setItem(i, 1, status_item)
            self.table.setItem(i, 2, privacy_item)
            self.table.setItem(i, 3, created_item)
            self.table.setItem(i, 4, link_item)
        self.table.resizeRowsToContents()

    def _selected(self) -> dict | None:
        row = self.table.currentRow()
        if 0 <= row < len(self._videos):
            return self._videos[row]
        return None

    def _update_preview(self) -> None:
        video = self._selected()
        if not video:
            self.preview_label.setText("Select a video to preview")
            return
        thumb = video.get("thumbnail_path") or ""
        if thumb and Path(thumb).exists():
            pixmap = QPixmap(str(thumb))
            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    280, 480,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_label.setPixmap(pixmap)
                return
        self.preview_label.setText("No thumbnail available")

    def _open_file(self) -> None:
        video = self._selected()
        if not video:
            return
        path = video.get("video_path") or ""
        if path and Path(path).exists():
            os.startfile(path)
        else:
            self.window.notify("Video file not found on disk")

    def _open_youtube(self) -> None:
        video = self._selected()
        if not video:
            return
        url = video.get("youtube_url") or ""
        if url:
            QDesktopServices.openUrl(QUrl(url))
        else:
            self.window.notify("No YouTube link for this video")

    def _retry(self) -> None:
        video = self._selected()
        if not video:
            return
        if self.window.queue_retry(video["id"]):
            self.window.navigate("dashboard")
