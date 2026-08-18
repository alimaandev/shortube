"""Desktop job manager: finish/progress/cancel signal flows via QThread."""

from __future__ import annotations

import time

import pytest

pytest.importorskip("PyQt6")

from shortube.db import Database
from shortube.desktop import workers
from shortube.pipeline import PipelineCancelled


def _wait(qapp, cond, timeout=8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def _fake_success_pipeline(topic, privacy="private", channel_id=None, dry_run=False,
                           video_id=None, progress_callback=None, cancel_event=None):
    progress_callback("Generating script...")
    progress_callback("Assembling video...")
    return {"url": "https://youtu.be/abc123"}


def test_job_flow_happy_path(monkeypatch, qapp, settings):
    monkeypatch.setattr(workers, "run_pipeline", _fake_success_pipeline)

    db = Database()
    tid = db.add_topic("test topic", niche="test")
    vid = db.create_video(tid, privacy="private")
    jid = db.create_job(vid, "manual")

    events = []
    jm = workers.JobManager()
    jm.jobQueued.connect(lambda j, t: events.append(("queued", j)))
    jm.jobStarted.connect(lambda j, t: events.append(("started", j)))
    jm.jobProgress.connect(lambda j, m, p: events.append(("progress", j, m, p)))
    jm.jobFinished.connect(lambda j, r: events.append(("finished", j, r)))
    jm.jobCancelled.connect(lambda j: events.append(("cancelled", j)))

    jm.submit(jid, vid, "test topic", "private")
    try:
        assert _wait(qapp, lambda: any(e[0] == "finished" for e in events))
        assert any(e[0] == "progress" and e[2] == "Generating script..." for e in events)
        assert db.get_job(jid)["status"] == "done"
        assert db.is_topic_used("test topic")
    finally:
        jm.shutdown()


def test_cancel_path(monkeypatch, qapp, settings):
    def fake_cancel_pipeline(topic, privacy="private", channel_id=None, dry_run=False,
                             video_id=None, progress_callback=None, cancel_event=None):
        while cancel_event is not None and not cancel_event.is_set():
            time.sleep(0.02)
        progress_callback("Generating script...")
        raise PipelineCancelled("cancelled")

    monkeypatch.setattr(workers, "run_pipeline", fake_cancel_pipeline)

    db = Database()
    tid = db.add_topic("cancel topic", niche="test")
    vid = db.create_video(tid, privacy="private")
    jid = db.create_job(vid, "manual")

    cancelled = []
    jm = workers.JobManager()
    jm.jobCancelled.connect(lambda j: cancelled.append(j))
    jm.submit(jid, vid, "cancel topic", "private")
    try:
        _wait(qapp, lambda: True, timeout=0.5)
        jm.cancel_current()
        assert _wait(qapp, lambda: bool(cancelled))
        assert db.get_job(jid)["status"] == "cancelled"
    finally:
        jm.shutdown()


def test_failure_path(monkeypatch, qapp, settings):
    def fake_fail_pipeline(*a, **kw):
        raise workers.PipelineError("assembly exploded")

    monkeypatch.setattr(workers, "run_pipeline", fake_fail_pipeline)

    db = Database()
    tid = db.add_topic("fail topic", niche="test")
    vid = db.create_video(tid, privacy="private")
    jid = db.create_job(vid, "manual")

    failed = []
    jm = workers.JobManager()
    jm.jobFailed.connect(lambda j, e: failed.append((j, e)))
    jm.submit(jid, vid, "fail topic", "private")
    try:
        assert _wait(qapp, lambda: bool(failed))
        assert failed[0][0] == jid
        assert "assembly exploded" in failed[0][1]
        assert db.get_job(jid)["status"] == "failed"
    finally:
        jm.shutdown()