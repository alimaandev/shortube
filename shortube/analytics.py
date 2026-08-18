from __future__ import annotations

import logging
import pickle
from datetime import UTC, datetime
from typing import Any

from googleapiclient.errors import HttpError

from shortube.db import Database
from shortube.upload import UploadError, _get_service

logger = logging.getLogger(__name__)

db = Database()


def fetch_video_stats(youtube_url: str) -> dict[str, Any]:
    if not youtube_url:
        return {}

    import re
    match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", youtube_url)
    if not match:
        return {}

    video_id = match.group(1)
    try:
        service = _get_service()
        resp = service.videos().list(
            part="statistics,snippet",
            id=video_id,
        ).execute()

        items = resp.get("items", [])
        if not items:
            return {}

        item = items[0]
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})

        return {
            "video_id": video_id,
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "shares": 0,
            "subscribers_gained": 0,
            "title": snippet.get("title", ""),
            "published_at": snippet.get("publishedAt", ""),
            "thumbnail": (snippet.get("thumbnails", {})
                          .get("high", {}).get("url", "")),
            "fetched_at": datetime.now(UTC).isoformat(),
        }
    except (UploadError, OSError, ValueError, pickle.PickleError, HttpError) as e:
        logger.warning("Failed to fetch stats for %s: %s", youtube_url, e)
        return {}


def refresh_all_analytics() -> list[dict[str, Any]]:
    videos = db.get_recent_videos(limit=100)
    results: list[dict[str, Any]] = []
    for v in videos:
        youtube_url = v.get("youtube_url")
        if not youtube_url:
            continue
        stats = fetch_video_stats(youtube_url)
        if stats:
            stats["video_db_id"] = v["id"]
            stats["topic_title"] = v.get("topic_title", "")
            results.append(stats)
    logger.info("Refreshed analytics for %d videos", len(results))
    return results
