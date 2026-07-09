from __future__ import annotations

import logging

import requests

from shortube.core.types import TrendIdea
from shortube.discovery.base import DiscoverySource
from shortube.shared.retry import retry

REDDIT_HOT = "https://old.reddit.com/r/{subreddit}/hot.json"
REDDIT_RISING = "https://old.reddit.com/r/{subreddit}/rising.json"
REDDIT_TOP = "https://old.reddit.com/r/{subreddit}/top.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

logger = logging.getLogger(__name__)

DEFAULT_SUBREDDITS = [
    "popular",
    "all",
    "explainlikeimfive",
    "todayilearned",
    "science",
    "technology",
    "interestingasfuck",
    "videos",
]


class RedditSource(DiscoverySource):
    name = "reddit"

    def __init__(self, subreddits: list[str] | None = None, min_score: int = 100):
        self._subreddits = subreddits or DEFAULT_SUBREDDITS
        self._min_score = min_score

    @retry(max_attempts=2, exceptions=(requests.RequestException,))
    def fetch(self, **kwargs) -> list[TrendIdea]:
        ideas: list[TrendIdea] = []
        for sub in self._subreddits:
            try:
                ideas.extend(self._fetch_subreddit(sub))
            except Exception as e:
                logger.warning("Reddit subreddit '%s' failed: %s", sub, e)
        return ideas

    def _fetch_subreddit(self, subreddit: str) -> list[TrendIdea]:
        urls = [
            REDDIT_HOT.format(subreddit=subreddit),
            REDDIT_TOP.format(subreddit=subreddit),
        ]
        ideas: list[TrendIdea] = []
        for url in urls:
            try:
                resp = requests.get(
                    url,
                    headers={"User-Agent": USER_AGENT},
                    params={"limit": 25, "raw_json": 1},
                    timeout=15,
                )
                if resp.status_code != 200:
                    logger.debug("Reddit %s returned %d", url, resp.status_code)
                    continue
            except Exception as e:
                logger.debug("Reddit request failed for %s: %s", url, e)
                continue
            data = resp.json()
            for post in data.get("data", {}).get("children", []):
                post_data = post.get("data", {})
                title = post_data.get("title", "")
                score = post_data.get("score", 0)
                if not title or score < self._min_score:
                    continue
                momentum = "rising" if "rising" in url else "stable"
                ideas.append(
                    TrendIdea(
                        title=title,
                        source="reddit",
                        score=min(score / 100.0, 10.0),
                        category=f"r/{subreddit}",
                        momentum=momentum,
                        url=post_data.get("url", ""),
                        reason=f"{score} upvotes on r/{subreddit}",
                    )
                )
        return ideas
