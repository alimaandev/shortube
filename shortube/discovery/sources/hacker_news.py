from __future__ import annotations

import logging

import requests

from shortube.core.types import TrendIdea
from shortube.discovery.base import DiscoverySource
from shortube.shared.retry import retry

HN_API = "https://hn.algolia.com/api/v1/search"
logger = logging.getLogger(__name__)


class HackerNewsSource(DiscoverySource):
    name = "hacker_news"

    def __init__(self, min_points: int = 10):
        self._min_points = min_points

    @retry(max_attempts=2, exceptions=(requests.RequestException,))
    def fetch(self, **kwargs) -> list[TrendIdea]:
        resp = requests.get(
            HN_API,
            params={
                "tags": "front_page",
                "hitsPerPage": 30,
            },
            headers={"User-Agent": "ShortsAutomator/1.0"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        ideas: list[TrendIdea] = []
        for hit in data.get("hits", []):
            title = hit.get("title", "")
            if not title:
                continue
            points = hit.get("points", 0)
            if points < self._min_points:
                continue
            momentum = "rising" if points >= 50 else "stable"
            ideas.append(
                TrendIdea(
                    title=title,
                    source="hacker_news",
                    score=min(points / 10.0, 10.0),
                    category="tech",
                    momentum=momentum,
                    url=hit.get("url") or hit.get("story_url") or "",
                    reason=f"{points} points on Hacker News",
                )
            )
        return ideas
