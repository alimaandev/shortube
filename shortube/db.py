from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shortube.config import get_settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        self._conn.executescript("""
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
        self._conn.commit()

    # ── Topics ────────────────────────────────────────────────────────

    def add_topic(
        self, title: str, niche: str = "", source: str = "",
        score: float = 0.0,
    ) -> int:
        slug = title.lower().replace(" ", "_")[:80]
        now = _now()
        self._conn.execute("""
            INSERT INTO topics (slug, title, niche, source, score, discovered_at, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
            ON CONFLICT(slug) DO UPDATE SET
                discovered_at = excluded.discovered_at,
                score = MAX(topics.score, excluded.score)
        """, (slug, title, niche, source, score, now))
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

    def get_unused_topics(self, niche: str = "", limit: int = 10) -> list[dict]:
        query = "SELECT * FROM topics WHERE status = 'pending'"
        params: list[Any] = []
        if niche:
            query += " AND niche = ?"
            params.append(niche)
        query += " ORDER BY score DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self._conn.execute(query, params).fetchall()]

    def get_topic_by_id(self, topic_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM topics WHERE id = ?", (topic_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_all_topics(self, limit: int = 100) -> list[dict]:
        return [
            dict(r) for r in self._conn.execute(
                "SELECT * FROM topics ORDER BY discovered_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        ]

    # ── Videos ────────────────────────────────────────────────────────

    def create_video(self, topic_id: int, privacy: str = "private") -> int:
        now = _now()
        cursor = self._conn.execute("""
            INSERT INTO videos (topic_id, privacy, status, created_at, updated_at)
            VALUES (?, ?, 'created', ?, ?)
        """, (topic_id, privacy, now, now))
        self._conn.commit()
        return cursor.lastrowid

    def update_video(self, video_id: int, **kwargs) -> None:
        kwargs["updated_at"] = _now()
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [video_id]
        self._conn.execute(f"UPDATE videos SET {sets} WHERE id = ?", vals)
        self._conn.commit()

    def get_video(self, video_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM videos WHERE id = ?", (video_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_recent_videos(self, limit: int = 20) -> list[dict]:
        return [
            dict(r) for r in self._conn.execute(
                "SELECT v.*, t.title as topic_title FROM videos v "
                "JOIN topics t ON v.topic_id = t.id "
                "ORDER BY v.created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        ]

    # ── Jobs ──────────────────────────────────────────────────────────

    def create_job(self, video_id: int, job_type: str) -> int:
        now = _now()
        cursor = self._conn.execute("""
            INSERT INTO jobs (video_id, job_type, status, created_at, updated_at)
            VALUES (?, ?, 'queued', ?, ?)
        """, (video_id, job_type, now, now))
        self._conn.commit()
        return cursor.lastrowid

    def update_job(self, job_id: int, **kwargs) -> None:
        kwargs["updated_at"] = _now()
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [job_id]
        self._conn.execute(f"UPDATE jobs SET {sets} WHERE id = ?", vals)
        self._conn.commit()

    def get_all_jobs(self, limit: int = 50) -> list[dict]:
        return [
            dict(r) for r in self._conn.execute(
                "SELECT j.*, t.title as topic_title FROM jobs j "
                "JOIN videos v ON j.video_id = v.id "
                "JOIN topics t ON v.topic_id = t.id "
                "ORDER BY j.created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        ]
