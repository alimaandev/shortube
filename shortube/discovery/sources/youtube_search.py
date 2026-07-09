from __future__ import annotations

import logging
from typing import Any

from shortube.config import NICHE
from shortube.core.types import TrendIdea
from shortube.discovery.base import DiscoverySource
from shortube.shared.retry import retry

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"

logger = logging.getLogger(__name__)

DEFAULT_QUERIES = [
    "trending now",
    "viral",
    "did you know",
    "facts",
    "how to",
    "why does",
    "science explained",
]


class YouTubeSearchSource(DiscoverySource):
    name = "youtube_search"

    def __init__(self, api_key: str = "", queries: list[str] | None = None):
        self._api_key = api_key
        self._queries = queries or DEFAULT_QUERIES

    def fetch(self, **kwargs) -> list[TrendIdea]:
        if not self._api_key:
            logger.warning("YouTube API key not set — skipping YouTube discovery")
            return []
        return self._search_trending()

    @retry(max_attempts=2, exceptions=(Exception,))
    def _search_trending(self) -> list[TrendIdea]:
        import requests

        ideas: list[TrendIdea] = []
        for query in self._queries[:3]:
            resp = requests.get(
                YOUTUBE_SEARCH_URL,
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "maxResults": 10,
                    "order": "viewCount",
                    "key": self._api_key,
                },
                headers={"User-Agent": "ShortsAutomator/1.0"},
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning("YouTube search returned %d for '%s'", resp.status_code, query)
                continue

            data = resp.json()
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                title = snippet.get("title", "")
                if not title:
                    continue
                ideas.append(
                    TrendIdea(
                        title=title,
                        source="youtube",
                        score=7.0,
                        category=snippet.get("channelTitle", "youtube"),
                        momentum="rising",
                        url=f"https://youtube.com/watch?v={item['id']['videoId']}",
                        reason=f"Trending on YouTube: {snippet.get('channelTitle', 'Unknown')}",
                    )
                )
        return ideas
