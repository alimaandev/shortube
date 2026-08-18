"""Facade between the UI and the database/job pipeline.

MainWindow stays a thin view: every DB mutation flows through
AppController so the write paths are testable without Qt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shortube.config import get_settings
from shortube.db import Database
from shortube.discover import discover


@dataclass
class QueuePick:
    """A queued generation request, ready for JobManager.submit."""

    job_id: int
    video_id: int
    topic: str
    privacy: str


@dataclass
class QueueResult:
    ok: bool
    error: str = ""
    pick: QueuePick | None = field(default=None)


class AppController:
    """Owns all DB write orchestration for the desktop app."""

    def __init__(self, db: Database | None = None) -> None:
        self._db = db or Database()

    def queue_generate(self, topic: str, niche: str, privacy: str) -> QueueResult:
        """Queue a manual generation for the given topic."""
        topic = topic.strip()
        if not topic:
            return QueueResult(ok=False, error="Enter a topic first")
        cfg = get_settings()
        niche_val = niche.strip() or cfg.niche
        tid = self._db.add_topic(topic, niche=niche_val)
        vid = self._db.create_video(tid, privacy=privacy)
        jid = self._db.create_job(vid, "manual")
        return QueueResult(
            ok=True, pick=QueuePick(job_id=jid, video_id=vid, topic=topic, privacy=privacy)
        )

    def queue_auto(self, niche: str, privacy: str) -> QueueResult:
        """Discover topics and queue the first one not used yet."""
        cfg = get_settings()
        niche_val = niche.strip() or cfg.niche
        ideas = discover(niche_val, max_results=5)
        for idea in ideas:
            if not self._db.is_topic_used(idea.title):
                tid = self._db.add_topic(
                    idea.title, niche=niche_val,
                    source=idea.source, score=idea.score,
                )
                vid = self._db.create_video(tid, privacy=privacy)
                jid = self._db.create_job(vid, "auto")
                return QueueResult(
                    ok=True,
                    pick=QueuePick(job_id=jid, video_id=vid, topic=idea.title, privacy=privacy),
                )
        return QueueResult(ok=False, error="No undiscovered topics found")

    def queue_retry(self, video_id: int) -> QueueResult:
        """Reset a video to pending and queue a retry job for it."""
        video = self._db.get_video(video_id)
        if not video:
            return QueueResult(ok=False, error="Video not found")
        topic = (video.topic_title or "").strip()
        if not topic:
            return QueueResult(ok=False, error="Video has no topic")
        privacy = video.privacy or "private"
        self._db.update_video(video_id, status="pending", error="")
        jid = self._db.create_job(video_id, "retry")
        return QueueResult(
            ok=True, pick=QueuePick(job_id=jid, video_id=video_id, topic=topic, privacy=privacy)
        )