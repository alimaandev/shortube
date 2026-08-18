"""Typed DB layer: row models, versioned migrations, update guards."""

from __future__ import annotations

import sqlite3

import pytest

from shortube.db import Database, JobRow, VideoRow


@pytest.fixture
def db(tmp_path) -> Database:
    return Database(tmp_path / "test.db")


def test_round_trip_creates_typed_rows(db):
    tid = db.add_topic("Typed DB Test Topic", niche="testing", source="pytest", score=4.2)
    vid = db.create_video(tid, privacy="private")

    video = db.get_video(vid)
    assert isinstance(video, VideoRow)
    assert video.topic_title == "Typed DB Test Topic"
    assert video.status == "created"
    assert video.privacy == "private"
    assert video.script_json is None

    db.update_video(vid, status="script_done", script_json='{"x": 1}')
    refreshed = db.get_video(vid)
    assert refreshed.status == "script_done"
    assert refreshed.script_json == '{"x": 1}'

    jid = db.create_job(vid, "manual")
    job = db.get_job(jid)
    assert isinstance(job, JobRow)
    assert job.status == "queued"
    assert job.topic_title == "Typed DB Test Topic"
    db.update_job(jid, status="running", progress=42)
    assert db.get_job(jid).progress == 42


def test_video_rows_are_immutable_models(db):
    tid = db.add_topic("Immutable")
    vid = db.create_video(tid)
    video = db.get_video(vid)
    assert VideoRow(**video.model_dump()).id == video.id


def test_update_video_rejects_unknown_columns(db):
    tid = db.add_topic("Guard")
    vid = db.create_video(tid)
    with pytest.raises(ValueError, match="Unknown video column"):
        db.update_video(vid, status="done", bogus_column="x")


def test_update_job_rejects_unknown_columns(db):
    tid = db.add_topic("Guard")
    vid = db.create_video(tid)
    jid = db.create_job(vid, "manual")
    with pytest.raises(ValueError, match="Unknown job column"):
        db.update_job(jid, progress=10, nope="x")


def test_fresh_db_reaches_latest_schema_version(db):
    conn = sqlite3.connect(str(db._path))
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version >= 3
    columns = {c[1] for c in conn.execute("PRAGMA table_info(videos)").fetchall()}
    assert {"storyboard_json", "music_path"} <= columns
    tables = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "kv" in tables
    conn.close()


def test_legacy_v1_database_upgrades_in_place(tmp_path):
    # Simulate a v1-era database (schema without storyboard_json/music_path).
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
            niche TEXT DEFAULT '', source TEXT DEFAULT '',
            score REAL DEFAULT 0.0, discovered_at TEXT NOT NULL,
            used_at TEXT, status TEXT DEFAULT 'pending'
        );
        CREATE TABLE videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER REFERENCES topics(id),
            script_json TEXT, voiceover_path TEXT, video_path TEXT,
            thumbnail_path TEXT, youtube_url TEXT,
            privacy TEXT DEFAULT 'private', status TEXT DEFAULT 'created',
            error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER REFERENCES videos(id), job_type TEXT NOT NULL,
            status TEXT DEFAULT 'queued', progress INTEGER DEFAULT 0,
            error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        PRAGMA user_version = 1;
    """)
    conn.commit()
    conn.close()

    db = Database(path)
    conn = sqlite3.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 3
    columns = {c[1] for c in conn.execute("PRAGMA table_info(videos)").fetchall()}
    assert {"storyboard_json", "music_path"} <= columns
    conn.close()

    # Existing v1 rows survive the upgrade untouched.
    tid = db.add_topic("Kept Topic")
    vid = db.create_video(tid)
    assert db.get_video(vid).topic_title == "Kept Topic"


def test_topic_slug_dedupe_and_scores(db):
    first = db.add_topic("Same Title", score=1.0)
    second = db.add_topic("Same Title", score=9.0)
    assert first == second
    assert db.is_topic_used("Same Title") is False
    db.mark_topic_used("Same Title")
    assert db.is_topic_used("Same Title") is True


def test_recent_videos_ordered_newest_first(db):
    ids = []
    for i in range(3):
        tid = db.add_topic(f"Topic {i}")
        ids.append(db.create_video(tid))
    recent = db.get_recent_videos()
    assert [v.id for v in recent[:3]] == ids[::-1]
    assert all(isinstance(v, VideoRow) for v in recent)