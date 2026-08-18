"""AppController facade: UI write paths without Qt."""

from __future__ import annotations

from shortube.db import Database
from shortube.desktop.app_controller import AppController
from shortube.types import TrendIdea


def _make_video(db, topic="controller topic", privacy="private"):
    tid = db.add_topic(topic, niche="test")
    vid = db.create_video(tid, privacy=privacy)
    db.update_video(vid, status="failed", error="boom")
    return vid


def test_queue_generate_creates_rows_and_job(settings):
    ctl = AppController()
    result = ctl.queue_generate("  New Manual Topic  ", "", "public")
    assert result.ok
    pick = result.pick
    assert pick.topic == "New Manual Topic"
    assert pick.privacy == "public"
    db = Database()
    video = db.get_video(pick.video_id)
    assert video.topic_title == "New Manual Topic"
    job = db.get_job(pick.job_id)
    assert job.video_id == pick.video_id
    assert job.job_type == "manual"


def test_queue_generate_rejects_empty_topic(settings):
    result = AppController().queue_generate("   ", "niche", "private")
    assert not result.ok
    assert "Enter a topic" in result.error


def test_queue_generate_uses_cfg_niche_when_empty(monkeypatch, settings):
    settings.niche = "fallback niche"
    monkeypatch.setattr("shortube.desktop.app_controller.get_settings", lambda: settings)
    captured: dict[str, str] = {}
    original = Database.add_topic

    def spy_add_topic(self, title, niche="", source="", score=0.0):
        captured["niche"] = niche
        return original(self, title, niche=niche, source=source, score=score)

    monkeypatch.setattr(Database, "add_topic", spy_add_topic)
    result = AppController().queue_generate("Topic A", "", "private")
    assert result.ok
    assert captured["niche"] == "fallback niche"


def test_queue_retry_resets_and_requeues(settings):
    db = Database()
    vid = _make_video(db)
    result = AppController().queue_retry(vid)
    assert result.ok
    assert result.pick.video_id == vid
    video = db.get_video(vid)
    assert video.status == "pending"
    assert video.error == ""
    job = db.get_job(result.pick.job_id)
    assert job.job_type == "retry"


def test_queue_retry_unknown_video(settings):
    result = AppController().queue_retry(999_999)
    assert not result.ok
    assert result.error == "Video not found"


def test_queue_auto_picks_first_unused(monkeypatch, settings):
    ideas = [
        TrendIdea(title="Used topic", source="rss", score=5.0),
        TrendIdea(title="Fresh topic", source="rss", score=8.0),
    ]
    monkeypatch.setattr("shortube.desktop.app_controller.discover", lambda niche, max_results: ideas)

    db = Database()
    tid = db.add_topic("Used topic", niche="test")
    db.create_video(tid)
    db.mark_topic_used("Used topic")

    result = AppController().queue_auto("", "private")
    assert result.ok
    assert result.pick.topic == "Fresh topic"
    assert db.get_job(result.pick.job_id).job_type == "auto"


def test_queue_auto_no_unused_topics(monkeypatch, settings):
    ideas = [TrendIdea(title="Only topic", source="rss", score=5.0)]
    monkeypatch.setattr("shortube.desktop.app_controller.discover", lambda niche, max_results: ideas)
    db = Database()
    tid = db.add_topic("Only topic", niche="test")
    db.create_video(tid)
    db.mark_topic_used("Only topic")

    result = AppController().queue_auto("", "private")
    assert not result.ok
    assert result.error == "No undiscovered topics found"