from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from shortube.core.types import TrendIdea
from shortube.discovery.base import DiscoverySource

logger = logging.getLogger(__name__)

DEFAULT_FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://www.theguardian.com/world/rss",
    "https://www.wired.com/feed/rss",
    "https://www.sciencedaily.com/rss/all.xml",
]


class RSSSource(DiscoverySource):
    name = "rss"

    def __init__(self, feed_urls: list[str] | None = None):
        self._feed_urls = feed_urls or DEFAULT_FEEDS

    def fetch(self, **kwargs) -> list[TrendIdea]:
        try:
            import feedparser
        except ImportError:
            logger.warning("feedparser not installed. Run: pip install feedparser")
            return []

        ideas: list[TrendIdea] = []
        for url in self._feed_urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:10]:
                    title = entry.get("title", "")
                    if not title:
                        continue
                    published = entry.get("published_parsed")
                    momentum = "rising"
                    if published:
                        age_hours = (
                            datetime.now(timezone.utc).timestamp() - 
                            datetime(*published[:6], tzinfo=timezone.utc).timestamp()
                        ) / 3600
                        momentum = "stable" if age_hours > 48 else "rising"
                    ideas.append(
                        TrendIdea(
                            title=title,
                            source="rss",
                            score=5.0,
                            category=feed.feed.get("title", "news") if hasattr(feed, "feed") else "news",
                            momentum=momentum,
                            url=entry.get("link", ""),
                            reason=f"From RSS: {feed.feed.get('title', url)}" if hasattr(feed, "feed") else "From RSS feed",
                        )
                    )
            except Exception as e:
                logger.warning("RSS feed '%s' failed: %s", url, e)
        return ideas
