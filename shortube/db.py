"""SQLite persistence with typed row models and versioned migrations.

The raw `sqlite3.Row` results are mapped into pydantic models so callers
never see untyped dicts, and schema changes go through an ordered
migration list tracked by `PRAGMA user_version`.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from shortube.config import get_settings

# ── Row models ────────────────────────────────────────────────────────


class TopicRow(BaseModel):
    id: int
    slug: str
    title: str
    niche: str = ""
    source: str = ""
    score: float = 0.0
    discovered_at: str
    used_at: str | None = None
    status: str = "pending"


class VideoRow(BaseModel):
    id: int
    topic_id: int | None = None
    topic_title: str = ""  # from the LEFT JOIN in queries
    script_json: str | None = None
    storyboard_json: str | None = None
    voiceover_path: str | None = None
    video_path: str | None = None
    thumbnail_path: str | None = None
    youtube_url: str | None = None
    privacy: str = "private"
    status: str = "created"
    error: str | None = None
    created_at: str
    updated_at: str
    music_path: str | None = None


class JobRow(BaseModel):
    id: int
    video_id: int | None = None
    job_type: str
    status: str = "queued"
    progress: int = 0
    error: str | None = None
    created_at: str
    updated_at: str
    topic_title: str = ""  # from the JOINs in queries


# ── Migrations (PRAGMA user_version = len applied) ────────────────────


def _migration_v1(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS topics (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            slug        TEXT UNIQUE NOT NULL,
            title       TEXT NOT NULL,
            niche       TEXT DEFAULT '',
            source      TEXT DEFAULT '',
            score       REAL DEFAULT 0.0,
            discovered_at TEXT NOT NULL,
            used_at     TEXT,
            status      TEXT DEFAULT 'pending'
        );

        CREATE TABLE IF NOT EXISTS videos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id        INTEGER REFERENCES topics(id),
            script_json     TEXT,
            voiceover_path  TEXT,
            video_path      TEXT,
            thumbnail_path  TEXT,
            youtube_url     TEXT,
            privacy         TEXT DEFAULT 'private',
            status          TEXT DEFAULT 'created',
            error           TEXT,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id    INTEGER REFERENCES videos(id),
            job_type    TEXT NOT NULL,
            status      TEXT DEFAULT 'queued',
            progress    INTEGER DEFAULT 0,
            error       TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_topics_slug ON topics(slug);
        CREATE INDEX IF NOT EXISTS idx_videos_topic_id ON videos(topic_id);
        CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
    """)


def _migration_v2(conn: sqlite3.Connection) -> None:
    # Idempotent: builds shipped before schema versioning already added
    # these columns via ad-hoc ALTERs, so only add what is missing.
    existing = {c[1] for c in conn.execute("PRAGMA table_info(videos)").fetchall()}
    for column in ("storyboard_json", "music_path"):
        if column not in existing:
            conn.execute(f"ALTER TABLE videos ADD COLUMN {column} TEXT")


def _migration_v3(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS kv (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


_MIGRATIONS: tuple[tuple[str, Callable[[sqlite3.Connection], None]], ...] = (
    ("initial schema", _migration_v1),
    ("video extra columns", _migration_v2),
    ("key-value settings store", _migration_v3),
)

_VIDEO_COLUMNS = frozenset({
    "topic_id", "script_json", "storyboard_json", "voiceover_path",
    "video_path", "thumbnail_path", "youtube_url", "privacy", "status",
    "error", "music_path",
})

_JOB_COLUMNS = frozenset({"video_id", "job_type", "status", "progress", "error"})


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = get_settings().base_dir / "shortube.db"
        self._path = Path(db_path)
        self._local = threading.local()
        self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._path))
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._conn
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        for target in range(version + 1, len(_MIGRATIONS) + 1):
            _MIGRATIONS[target - 1][1](conn)
            conn.execute(f"PRAGMA user_version = {target}")
        conn.commit()

    # ── Topics ────────────────────────────────────────────────────────

    def add_topic(
        self, title: str, niche: str = "", source: str = "",
        score: float = 0.0,
    ) -> int:
        slug = title.lower().replace(" ", "_")[:80]
        self._conn.execute("""
            INSERT INTO topics (slug, title, niche, source, score, discovered_at, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
            ON CONFLICT(slug) DO UPDATE SET
                discovered_at = excluded.discovered_at,
                score = MAX(topics.score, excluded.score)
        """, (slug, title, niche, source, score, _now()))
        self._conn.commit()
        row = self._conn.execute(
            "SELECT id FROM topics WHERE slug = ?", (slug,)
        ).fetchone()
        return row["id"] if row else 0

    def is_topic_used(self, title: str) -> bool:
        slug = title.lower().replace(" ", "_")[:80]
        row = self._conn.execute(
            "SELECT 1 FROM topics WHERE slug = ? AND status IN ('done','uploaded')",
            (slug,),
        ).fetchone()
        return row is not None

    def mark_topic_used(self, title: str) -> None:
        slug = title.lower().replace(" ", "_")[:80]
        self._conn.execute(
            "UPDATE topics SET status = 'done', used_at = ? WHERE slug = ?",
            (_now(), slug),
        )
        self._conn.commit()

    # ── Videos ────────────────────────────────────────────────────────

    def create_video(self, topic_id: int, privacy: str = "private") -> int:
        now = _now()
        cursor = self._conn.execute("""
            INSERT INTO videos (topic_id, privacy, status, created_at, updated_at)
            VALUES (?, ?, 'created', ?, ?)
        """, (topic_id, privacy, now, now))
        self._conn.commit()
        return cursor.lastrowid

    def update_video(self, video_id: int, **kwargs: str | int | None) -> None:
        unknown = set(kwargs) - _VIDEO_COLUMNS
        if unknown:
            raise ValueError(f"Unknown video column(s): {sorted(unknown)}")
        kwargs = {**kwargs, "updated_at": _now()}
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        self._conn.execute(f"UPDATE videos SET {sets} WHERE id = ?",
                           [*kwargs.values(), video_id])
        self._conn.commit()

    def get_video(self, video_id: int) -> VideoRow | None:
        row = self._conn.execute(
            "SELECT v.*, t.title AS topic_title FROM videos v "
            "LEFT JOIN topics t ON v.topic_id = t.id "
            "WHERE v.id = ?", (video_id,)
        ).fetchone()
        return VideoRow(**dict(row)) if row else None

    def get_recent_videos(self, limit: int = 20) -> list[VideoRow]:
        rows = self._conn.execute(
            "SELECT v.*, t.title AS topic_title FROM videos v "
            "JOIN topics t ON v.topic_id = t.id "
            "ORDER BY v.created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [VideoRow(**dict(r)) for r in rows]

    # ── Jobs ──────────────────────────────────────────────────────────

    def create_job(self, video_id: int, job_type: str) -> int:
        now = _now()
        cursor = self._conn.execute("""
            INSERT INTO jobs (video_id, job_type, status, created_at, updated_at)
            VALUES (?, ?, 'queued', ?, ?)
        """, (video_id, job_type, now, now))
        self._conn.commit()
        return cursor.lastrowid

    def update_job(self, job_id: int, **kwargs: str | int | None) -> None:
        unknown = set(kwargs) - _JOB_COLUMNS
        if unknown:
            raise ValueError(f"Unknown job column(s): {sorted(unknown)}")
        kwargs = {**kwargs, "updated_at": _now()}
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        self._conn.execute(f"UPDATE jobs SET {sets} WHERE id = ?",
                           [*kwargs.values(), job_id])
        self._conn.commit()

    def get_job(self, job_id: int) -> JobRow | None:
        row = self._conn.execute(
            "SELECT j.*, t.title AS topic_title FROM jobs j "
            "JOIN videos v ON j.video_id = v.id "
            "JOIN topics t ON v.topic_id = t.id "
            "WHERE j.id = ?", (job_id,)
        ).fetchone()
        return JobRow(**dict(row)) if row else None

    # ── Key-value settings ────────────────────────────────────────────

    def get_kv(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM kv WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def set_kv(self, key: str, value: str) -> None:
        self._conn.execute("""
            INSERT INTO kv (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        self._conn.commit()

    def delete_kv(self, key: str) -> None:
        self._conn.execute("DELETE FROM kv WHERE key = ?", (key,))
        self._conn.commit()
