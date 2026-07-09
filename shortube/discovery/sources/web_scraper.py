from __future__ import annotations

import logging
import re
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import urlparse

import requests

from shortube.core.types import TrendIdea
from shortube.discovery.base import DiscoverySource
from shortube.shared.retry import retry

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}


# ── HTML parsers ──────────────────────────────────────────────────────

class TitleExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_title = False
        self.title = ""

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data.strip()


class GitHubTrendingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_h2 = False
        self._in_article = False
        self._in_desc = False
        self._capture_p = False
        self._current_repo = ""
        self._current_desc = ""
        self.repos: list[tuple[str, str]] = []
        self._tag_stack: list[str] = []

    def handle_starttag(self, tag, attrs):
        self._tag_stack.append(tag)
        attrs_dict = dict(attrs)
        if tag == "article":
            self._in_article = True
            self._current_repo = ""
            self._current_desc = ""
        if tag == "h2" and self._in_article:
            self._in_h2 = True
        if tag == "p" and self._in_article:
            class_ = attrs_dict.get("class", "")
            if "col-9" in class_ or "pr-4" in class_:
                self._in_desc = True

    def handle_endtag(self, tag):
        self._tag_stack.pop()
        if tag == "article" and self._in_article and self._current_repo:
            self.repos.append((self._current_repo.strip(), self._current_desc.strip()))
            self._in_article = False
        if tag == "h2":
            self._in_h2 = False
        if tag == "p":
            self._in_desc = False

    def handle_data(self, data):
        if self._in_h2 and self._in_article:
            text = data.strip()
            if text and "/" in text:
                self._current_repo = text
        if self._in_desc:
            self._current_desc += data.strip() + " "


# ── Site-specific parsers ─────────────────────────────────────────────

def _parse_hn_html(html: str) -> list[TrendIdea]:
    ideas: list[TrendIdea] = []
    # Extract story titles from HN's table structure
    title_lines = re.findall(r'class="titleline"[^>]*><a[^>]*>([^<]+)</a>', html)
    for i, title in enumerate(title_lines):
        ideas.append(
            TrendIdea(
                title=title.strip(),
                source="hacker_news",
                score=max(10.0 - i * 0.3, 2.0),
                category="tech",
                momentum="rising" if i < 5 else "stable",
                url="https://news.ycombinator.com/",
                reason=f"Position #{i + 1} on Hacker News front page",
            )
        )
    return ideas


def _parse_lobsters_json(data: dict | list) -> list[TrendIdea]:
    ideas: list[TrendIdea] = []
    if isinstance(data, list):
        items = data
    else:
        items = data.get("data", [])
    for item in items:
        title = item.get("title", "") or item.get("description", "")
        url = item.get("url", "") or item.get("link", "")
        score = item.get("score", 0) or item.get("points", 0)
        if not title:
            continue
        ideas.append(
            TrendIdea(
                title=title.strip(),
                source="lobsters",
                score=min(int(score) / 10.0, 10.0) if score else 5.0,
                category="tech",
                momentum="rising",
                url=url,
                reason=f"On lobste.rs" + (f" ({score} points)" if score else ""),
            )
        )
    return ideas


def _parse_github_trending(html: str) -> list[TrendIdea]:
    parser = GitHubTrendingParser()
    parser.feed(html)
    ideas: list[TrendIdea] = []
    for repo, desc in parser.repos:
        title = f"{repo}: {desc[:100]}" if desc else repo
        ideas.append(
            TrendIdea(
                title=title.strip(),
                source="github",
                score=7.0,
                category="tech",
                momentum="rising",
                url=f"https://github.com/{repo}",
                reason=f"Trending on GitHub",
            )
        )
    return ideas


# ── Dev.to ─────────────────────────────────────────────────────────────

def _parse_devto_json(data: dict) -> list[TrendIdea]:
    ideas: list[TrendIdea] = []
    articles = data if isinstance(data, list) else data.get("data", [])
    for article in articles:
        title = article.get("title", "")
        if not title:
            continue
        tags = article.get("tag_list", [])
        url = article.get("url", "") or article.get("link", "")
        score = article.get("positive_reactions_count", 0) or 0
        ideas.append(
            TrendIdea(
                title=title.strip(),
                source="devto",
                score=min(score / 5.0, 10.0),
                category=tags[0] if tags else "tech",
                momentum="rising",
                url=url,
                reason=f"Dev.to article" + (f" ({score} reactions)" if score else ""),
            )
        )
    return ideas


# ── Hackaday ───────────────────────────────────────────────────────────

class HackadayParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_article = False
        self._in_h1 = False
        self._current_entry: dict = {}
        self.entries: list[dict] = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "article":
            self._in_article = True
            self._current_entry = {}
        if tag == "h1" and self._in_article:
            self._in_h1 = True
            self._current_entry["title"] = ""
        if tag == "a" and self._in_article and "href" in attrs_dict:
            href = attrs_dict["href"]
            if "hackaday.com" in href and not self._current_entry.get("url"):
                self._current_entry["url"] = href

    def handle_endtag(self, tag):
        if tag == "article" and self._in_article:
            if self._current_entry.get("title"):
                self.entries.append(self._current_entry)
            self._in_article = False
            self._current_entry = {}
        if tag == "h1":
            self._in_h1 = False

    def handle_data(self, data):
        if self._in_h1:
            self._current_entry["title"] = (self._current_entry.get("title", "") + data.strip()).strip()


def _parse_hackaday(html: str) -> list[TrendIdea]:
    parser = HackadayParser()
    parser.feed(html)
    ideas: list[TrendIdea] = []
    for entry in parser.entries[:20]:
        title = entry.get("title", "")
        url = entry.get("url", "")
        if not title:
            continue
        ideas.append(
            TrendIdea(
                title=title.strip(),
                source="hackaday",
                score=6.0,
                category="hardware",
                momentum="rising",
                url=url,
                reason="Hackaday blog post",
            )
        )
    return ideas


# ── Wikipedia Current Events ──────────────────────────────────────────

SKIP_WIKI_PREFIXES = [
    "This portal's subpages", "Worldwide current events", "Entry views by week",
    "Today's most viewed", "Sports events", "Ongoing", "Recently died",
    "Selected anniversaries", "In the news",
]


def _parse_wikipedia_current_events(html: str) -> list[TrendIdea]:
    ideas: list[TrendIdea] = []
    # Find the mw-parser-output content div
    mpo = re.search(r'<div[^>]*class="mw-parser-output"[^>]*>', html, re.I)
    if not mpo:
        return ideas
    content_start = mpo.end()

    # Extract <li> items within the content area only (within ~100k chars after mw-parser-output)
    lis = re.findall(r'<li>(.*?)</li>', html[content_start:content_start + 100000], re.DOTALL)
    for li in lis:
        text = re.sub(r'<[^>]+>', '', li).strip()
        if not text or len(text) < 30:
            continue
        # Skip navigation / section header items
        if any(text.startswith(p) for p in SKIP_WIKI_PREFIXES):
            continue
        ideas.append(
            TrendIdea(
                title=text[:150].strip(),
                source="wikipedia",
                score=5.0,
                category="current_events",
                momentum="rising",
                url="https://en.wikipedia.org/wiki/Portal:Current_events",
                reason="Current events on Wikipedia",
            )
        )
    return ideas


# ── Ars Technica ───────────────────────────────────────────────────────

class ArsTechnicaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_article = False
        self._in_h2 = False
        self._current_title = ""
        self.titles: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "article":
            self._in_article = True
            self._current_title = ""
        if tag == "h2" and self._in_article:
            self._in_h2 = True
            self._current_title = ""

    def handle_endtag(self, tag):
        if tag == "h2" and self._in_h2:
            if self._current_title.strip():
                self.titles.append(self._current_title.strip())
            self._in_h2 = False
            self._current_title = ""
        if tag == "article":
            self._in_article = False

    def handle_data(self, data):
        if self._in_h2:
            self._current_title += data.strip()


def _parse_arstechnica(html: str) -> list[TrendIdea]:
    parser = ArsTechnicaParser()
    parser.feed(html)
    ideas: list[TrendIdea] = []
    for title in parser.titles:
        ideas.append(
            TrendIdea(
                title=title.strip(),
                source="arstechnica",
                score=6.0,
                category="tech",
                momentum="rising",
                url="https://arstechnica.com/",
                reason="Article on Ars Technica",
            )
        )
    return ideas


# ── Target registry ───────────────────────────────────────────────────

TargetHandler = tuple[str, str, Callable[[str | dict | list], list[TrendIdea]]]
# (url, content_type, parser)

DEFAULT_TARGETS: list[TargetHandler] = [
    ("https://lobste.rs/newest.json", "json", _parse_lobsters_json),
    ("https://github.com/trending", "html", _parse_github_trending),
    ("https://dev.to/api/articles?per_page=30", "json", _parse_devto_json),
    ("https://hackaday.com/blog/", "html", _parse_hackaday),
    ("https://en.wikipedia.org/wiki/Portal:Current_events", "html", _parse_wikipedia_current_events),
    ("https://arstechnica.com/", "html", _parse_arstechnica),
]


# ── Source ────────────────────────────────────────────────────────────

class WebScraperSource(DiscoverySource):
    name = "web_scraper"

    def __init__(self, targets: list[TargetHandler] | None = None):
        self._targets = targets or DEFAULT_TARGETS

    def fetch(self, **kwargs) -> list[TrendIdea]:
        ideas: list[TrendIdea] = []
        for url, content_type, parser in self._targets:
            try:
                ideas.extend(self._fetch_and_parse(url, content_type, parser))
            except Exception as e:
                logger.warning("Scrape of '%s' failed: %s", url, e)
        return ideas

    @retry(max_attempts=2, exceptions=(requests.RequestException,))
    def _fetch_and_parse(
        self,
        url: str,
        content_type: str,
        parser: Callable,
    ) -> list[TrendIdea]:
        resp = requests.get(url, timeout=15, headers=HEADERS)
        resp.raise_for_status()

        if content_type == "json":
            data = resp.json()
        else:
            data = resp.text

        return parser(data)
