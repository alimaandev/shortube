from __future__ import annotations

import logging
import re

import feedparser
import requests

from shortube.config import get_settings
from shortube.llm import LLMError, create_llm
from shortube.types import TrendIdea

logger = logging.getLogger(__name__)


_HEADERS = {"User-Agent": "ShortsAutomator/1.0"}


_REFINE_PROMPT = """You are a YouTube Shorts topic strategist for the niche: {niche}.

Here are trending headlines found online:
{titles}

Rewrite the best candidates into catchy YouTube Shorts topics for this niche.
Rules:
- Only keep topics relevant to the niche; drop everything irrelevant
- Max 6 words per topic, curiosity-driven and specific
- No clickbait lies and no sensationalism
- Keep at most {max_topics} topics

Return ONLY valid JSON:
{{
    "topics": [
        {{"title": "string", "reason": "short explanation why this will perform"}}
    ]
}}"""


def _word_overlap(a: str, b: str) -> float:
    wa = set(re.findall(r"\b[a-z0-9']+\b", a.lower()))
    wb = set(re.findall(r"\b[a-z0-9']+\b", b.lower()))
    if not wa:
        return 0.0
    return len(wa & wb) / len(wa)


def refine_topics(ideas: list[TrendIdea], niche: str, max_results: int) -> list[TrendIdea]:
    """Use the LLM to turn scraped headlines into niche-specific Shorts topics.

    Never blocks discovery: any LLM failure falls back to the raw ideas.
    """
    cfg = get_settings()
    if not ideas or not niche:
        return ideas[:max_results]
    try:
        if cfg.llm_provider == "ollama":
            api_key = ""
        else:
            api_key = cfg.groq_api_key if cfg.llm_provider == "groq" else cfg.openrouter_api_key
        llm = create_llm(
            provider=cfg.llm_provider,
            api_key=api_key,
            model=cfg.discovery_model or cfg.llm_model,
        )
        titles = "\n".join(f"- {i.title[:120]}" for i in ideas[:15])
        raw = llm.generate_json(
            "You are a YouTube Shorts topic strategist. Output valid JSON only.",
            _REFINE_PROMPT.format(
                niche=niche, titles=titles, max_topics=max_results
            ),
            temperature=cfg.llm_temperature,
            max_tokens=600,
        )
        topics = raw.get("topics", [])
        if not isinstance(topics, list) or not topics:
            return ideas[:max_results]

        refined: list[TrendIdea] = []
        for i, item in enumerate(topics):
            if not isinstance(item, dict):
                continue
            title = re.sub(r"\s+", " ", str(item.get("title", "")).strip())
            if not title or len(title.split()) > 10:
                continue
            reason = str(item.get("reason", ""))[:120]
            original = max(ideas, key=lambda x: _word_overlap(title, x.title))
            if original and _word_overlap(title, original.title) >= 0.5:
                refined.append(TrendIdea(
                    title=title,
                    source=original.source,
                    score=original.score + 1.0,
                    url=original.url,
                    reason=reason,
                ))
            else:
                refined.append(TrendIdea(
                    title=title,
                    source="llm",
                    score=max(3.0, 10.0 - i),
                    reason=reason,
                ))
        logger.info("LLM refined %d topics for niche '%s'", len(refined), niche)
        return refined[:max_results]
    except (LLMError, ValueError, TypeError, OSError) as e:
        logger.warning("LLM topic refinement failed (%s) — using raw titles", e)
        return ideas[:max_results]


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
    except (requests.RequestException, KeyError, TypeError) as e:
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
        except (OSError, ValueError, TypeError) as e:
            logger.warning("RSS feed %s failed: %s", url, e)
    return ideas


def _youtube_search(niche: str = "") -> list[TrendIdea]:
    import os
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if not api_key:
        return []

    cfg = get_settings()
    query = niche or cfg.niche
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": query,
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
    except (requests.RequestException, KeyError, TypeError) as e:
        logger.warning("YouTube search failed: %s", e)
        return []


_SOURCES = {
    "hackernews": _hacker_news,
    "rss": _rss_feeds,
    "youtube": _youtube_search,
}


def discover(niche: str = "", max_results: int = 10) -> list[TrendIdea]:
    all_ideas: list[TrendIdea] = []

    for name, fetcher in _SOURCES.items():
        try:
            ideas = fetcher(niche) if name == "youtube" else fetcher()
            all_ideas.extend(ideas)
            logger.info("Got %d ideas from %s", len(ideas), name)
        except (requests.RequestException, OSError, KeyError, TypeError, ValueError) as e:
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

    # LLM refinement: turn headlines into niche-specific Shorts topics
    return refine_topics(diverse, niche, max_results)
