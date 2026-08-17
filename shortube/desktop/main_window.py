from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from shortube.config import get_settings
from shortube.desktop.pages.analytics import AnalyticsPage
from shortube.desktop.pages.dashboard import DashboardPage
from shortube.desktop.pages.schedule import SchedulePage
from shortube.desktop.pages.settings import SettingsPage
from shortube.desktop.pages.trends import TrendsPage
from shortube.desktop.pages.videos import VideosPage
from shortube.desktop.workers import JobManager
from shortube.scheduler import get_schedule_config

NAV_ITEMS = [
    ("dashboard", "Dashboard"),
    ("trends", "Trends"),
    ("videos", "Videos"),
    ("settings", "Settings"),
    ("schedule", "Schedule"),
    ("analytics", "Analytics"),
]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Shortube Studio")
        self.resize(1240, 800)
        self.setMinimumSize(980, 640)

        self.jobs = JobManager(self)
        self.apply_theme()

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 20, 12, 16)
        sidebar_layout.setSpacing(4)

        app_title = QLabel("Shortube")
        app_title.setObjectName("appTitle")
        subtitle = QLabel("Studio")
        subtitle.setObjectName("appSubtitle")
        sidebar_layout.addWidget(app_title)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addSpacing(24)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        for key, label in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._nav_group.addButton(btn)
            sidebar_layout.addWidget(btn)
        sidebar_layout.addStretch(1)

        self._scheduler_label = QLabel()
        self._scheduler_label.setObjectName("appSubtitle")
        self._scheduler_label.setWordWrap(True)
        sidebar_layout.addWidget(self._scheduler_label)
        self._update_scheduler_label()

        self._stack = QStackedWidget()
        self._pages: dict[str, QWidget] = {}
        self._pages["dashboard"] = DashboardPage(self)
        self._pages["trends"] = TrendsPage(self)
        self._pages["videos"] = VideosPage(self)
        self._pages["settings"] = SettingsPage(self)
        self._pages["schedule"] = SchedulePage(self)
        self._pages["analytics"] = AnalyticsPage(self)
        for key, _ in NAV_ITEMS:
            self._stack.addWidget(self._pages[key])

        root_layout.addWidget(sidebar)
        root_layout.addWidget(self._stack, 1)
        self.setCentralWidget(root)

        for i, (key, _) in enumerate(NAV_ITEMS):
            self._nav_group.buttons()[i].clicked.connect(
                lambda _=False, idx=i: self._stack.setCurrentIndex(idx)
            )
        self._nav_group.buttons()[0].setChecked(True)

        self.jobs.queueLengthChanged.connect(
            lambda n: self.statusBar().showMessage(
                f"Queue: {n} job(s) waiting" if n > 0 else ""
            )
        )
        self.statusBar().showMessage("Ready")

    def _update_scheduler_label(self) -> None:
        cfg = get_schedule_config()
        if cfg.get("running"):
            self._scheduler_label.setText(
                f"Schedule: every {cfg.get('interval_hours', 6)}h "
                f"({cfg.get('generated_today', 0)}/{cfg.get('max_daily', 4)} today)"
            )
        else:
            self._scheduler_label.setText("Schedule: off")

    def apply_theme(self) -> None:
        from PyQt6.QtWidgets import QApplication

        from shortube.desktop.theme import build_stylesheet

        QApplication.instance().setStyleSheet(build_stylesheet())

    def refresh_scheduler_label(self) -> None:
        self._update_scheduler_label()

    def navigate(self, key: str) -> None:
        for i, (nav_key, _) in enumerate(NAV_ITEMS):
            if nav_key == key:
                self._stack.setCurrentIndex(i)
                self._nav_group.buttons()[i].setChecked(True)
                return

    def notify(self, message: str, timeout_ms: int = 5000) -> None:
        self.statusBar().showMessage(message, timeout_ms)

    def queue_generate(self, topic: str, niche: str, privacy: str) -> bool:
        from shortube.db import Database

        topic = topic.strip()
        if not topic:
            self.notify("Enter a topic first")
            return False
        cfg = get_settings()
        niche_val = niche.strip() or cfg.niche
        db = Database()
        tid = db.add_topic(topic, niche=niche_val)
        vid = db.create_video(tid, privacy=privacy)
        jid = db.create_job(vid, "manual")
        self.jobs.submit(jid, vid, topic, privacy)
        self.notify(f"Queued: {topic[:50]}")
        return True

    def queue_auto(self, niche: str, privacy: str) -> None:
        from shortube.db import Database
        from shortube.discover import discover

        cfg = get_settings()
        niche_val = niche.strip() or cfg.niche
        self.notify("Discovering topics...")

        def work() -> list[dict]:
            db = Database()
            ideas = discover(niche_val, max_results=5)
            for idea in ideas:
                if not db.is_topic_used(idea.title):
                    tid = db.add_topic(
                        idea.title, niche=niche_val,
                        source=idea.source, score=idea.score,
                    )
                    vid = db.create_video(tid, privacy=privacy)
                    jid = db.create_job(vid, "auto")
                    return {"jid": jid, "vid": vid, "topic": idea.title}
            return {}

        def done(pick: dict) -> None:
            if not pick:
                self.notify("No undiscovered topics found")
                return
            self.jobs.submit(pick["jid"], pick["vid"], pick["topic"], privacy)
            self.notify(f"Auto: queued '{pick['topic'][:50]}'")

        from shortube.desktop.workers import run_in_thread
        run_in_thread(work, done, on_error=lambda err: self.notify(f"Auto failed: {err}"))

    def queue_retry(self, video_id: int) -> bool:
        from shortube.db import Database

        db = Database()
        video = db.get_video(video_id)
        if not video:
            self.notify("Video not found")
            return False
        topic = (video.get("topic_title") or "").strip()
        if not topic:
            self.notify("Video has no topic")
            return False
        privacy = video.get("privacy") or "private"
        db.update_video(video_id, status="pending", error="")
        jid = db.create_job(video_id, "retry")
        self.jobs.submit(jid, video_id, topic, privacy)
        self.notify(f"Retrying: {topic[:50]}")
        return True

    def closeEvent(self, event) -> None:
        self.jobs.shutdown()
        super().closeEvent(event)
