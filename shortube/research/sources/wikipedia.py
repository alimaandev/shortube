from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote

import requests

from shortube.core.exceptions import ResearchError
from shortube.core.types import Fact, Source
from shortube.shared.retry import retry

logger = logging.getLogger(__name__)

WIKI_API_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
WIKI_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "ShortsAutomator/1.0 (research bot; https://github.com/shortube)"}


class WikipediaSource:
    name = "wikipedia"

    def fetch(self, topic: str, max_results: int = 3) -> list[Fact]:
        pages = self._search(topic, max_results)
        facts: list[Fact] = []
        for title in pages:
            try:
                summary = self._get_summary(title)
                if summary:
                    facts.append(
                        Fact(
                            statement=summary,
                            source=f"Wikipedia: {title}",
                            confidence=0.8,
                            url=f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
                        )
                    )
            except Exception as e:
                logger.warning("Wikipedia fetch failed for '%s': %s", title, e)
        return facts

    @retry(max_attempts=2, exceptions=(requests.RequestException,))
    def _search(self, topic: str, max_results: int) -> list[str]:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": topic,
            "srlimit": max_results,
            "format": "json",
        }
        resp = requests.get(WIKI_SEARCH_URL, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [item["title"] for item in data.get("query", {}).get("search", [])]

    @retry(max_attempts=2, exceptions=(requests.RequestException,))
    def _get_summary(self, title: str) -> str | None:
        url = WIKI_API_URL.format(title=quote(title.replace(" ", "_")))
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        summary = data.get("extract", "")
        # Clean up HTML tags
        summary = re.sub(r"<[^>]+>", "", summary)
        return summary[:2000] if summary else None
