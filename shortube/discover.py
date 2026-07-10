from __future__ import annotations

import logging
from typing import Any

import feedparser
import requests

from shortube.config import get_settings
from shortube.types import TrendIdea

logger = logging.getLogger(__name__)


_HEADERS = {"User-Agent": "ShortsAutomator/1.0"}


# ── Source scrapers ──────────────────────────────────────────────────

def _hacker_news() -> list[TrendIdea]:
    try:
        resp = requests.get(
            "https://hn.algolia.com/api/v1/search?"
            "tags=front_page&hitsPerPage=30",
            timeout=15, headers=_HEADERS,
        )
        return [
            TrendIdea(
                title=item["title"],
                source="hackernews",
                score=item.get("points", 0) / 10.0,
                url=item.get("url") or
                    f"https://news.ycombinator.com/item?id={item['objectID']}",
            )
            for item in resp.json().get("hits", [])
            if item.get("title")
        ]
    except Exception as e:
        logger.warning("Hacker News failed: %s", e)
        return []


def _rss_feeds() -> list[TrendIdea]:
    feeds = [
        "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://www.theverge.com/rss/index.xml",
        "https://www.wired.com/feed/rss",
        "https://arstechnica.com/feed/",
    ]
    ideas: list[TrendIdea] = []
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                title = entry.get("title", "")
                if title:
                    ideas.append(TrendIdea(
                        title=title,
                        source="rss",
                        score=3.0,
                        url=entry.get("link"),
                    ))
        except Exception as e:
            logger.warning("RSS feed %s failed: %s", url, e)
    return ideas


def _youtube_search() -> list[TrendIdea]:
    import os
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if not api_key:
        return []

    cfg = get_settings()
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": cfg.niche,
                "type": "video",
                "order": "viewCount",
                "maxResults": 10,
                "relevanceLanguage": "en",
                "key": api_key,
            },
            timeout=15, headers=_HEADERS,
        )
        return [
            TrendIdea(
                title=item["snippet"]["title"],
                source="youtube",
                score=4.0,
                url=(
                    "https://www.youtube.com/watch?v="
                    f"{item['id']['videoId']}"
                ),
            )
            for item in resp.json().get("items", [])
            if item.get("id", {}).get("videoId")
        ]
    except Exception as e:
        logger.warning("YouTube search failed: %s", e)
        return []


_SOURCES = {
    "hackernews": _hacker_news,
    "rss": _rss_feeds,
    "youtube": _youtube_search,
}


# ── Public API ───────────────────────────────────────────────────────

class DiscoveryError(Exception):
    pass


def discover(niche: str = "", max_results: int = 10) -> list[TrendIdea]:
    all_ideas: list[TrendIdea] = []

    for name, fetcher in _SOURCES.items():
        try:
            ideas = fetcher()
            all_ideas.extend(ideas)
            logger.info("Got %d ideas from %s", len(ideas), name)
        except Exception as e:
            logger.warning("Source '%s' failed: %s", name, e)

    # Deduplicate by title similarity
    seen: set[str] = set()
    unique: list[TrendIdea] = []
    for idea in all_ideas:
        key = idea.title.lower().strip()[:60]
        if key not in seen:
            seen.add(key)
            unique.append(idea)

    # Score and rank
    unique.sort(key=lambda x: x.score, reverse=True)

    # Diversify across sources
    counts: dict[str, int] = {}
    max_per = max(2, len(unique) // max(len(_SOURCES), 1) + 1)
    diverse: list[TrendIdea] = []
    for idea in unique:
        if counts.get(idea.source, 0) < max_per:
            counts[idea.source] = counts.get(idea.source, 0) + 1
            diverse.append(idea)
            if len(diverse) >= max_results:
                break

    return diverse[:max_results]
