from __future__ import annotations

import logging
from typing import Sequence

from shortube.config import NICHE
from shortube.core.types import TrendIdea
from shortube.discovery.deduplicator import deduplicate_ideas
from shortube.discovery.scorer import Scorer
from shortube.discovery.sources import ALL_SOURCES
from shortube.shared.cache import DiskCache
from shortube.shared.llm import LLMProvider
from shortube.shared.logging import get_logger

logger = logging.getLogger(__name__)


class DiscoveryEngine:
    def __init__(
        self,
        llm: LLMProvider | None = None,
        cache: DiskCache | None = None,
        niche: str = "",
    ):
        self._llm = llm
        self._cache = cache
        self._niche = niche or NICHE
        self._logger = get_logger("discovery")
        self._scorer = Scorer(llm)

        # Active sources (registered by name)
        self._sources: dict[str, object] = {}

    def register_source(self, name: str, source: object) -> DiscoveryEngine:
        self._sources[name] = source
        return self

    def register_defaults(self) -> DiscoveryEngine:
        for name, cls in ALL_SOURCES.items():
            try:
                kwargs = {}
                if name == "youtube_search":
                    import os
                    api_key = os.getenv("YOUTUBE_API_KEY", "")
                    if not api_key:
                        self._logger.info("YOUTUBE_API_KEY not set — skipping YouTube search source")
                        continue
                    kwargs["api_key"] = api_key
                self._sources[name] = cls(**kwargs)
            except Exception as e:
                self._logger.warning("Failed to register source '%s': %s", name, e)
        return self

    def _diversify(
        self,
        scored: list[TrendIdea],
        max_results: int,
    ) -> list[TrendIdea]:
        count = max(len(self._sources), 1)
        max_per_source = max(2, int(max_results / count) + 1)
        source_counts: dict[str, int] = {}
        diverse: list[TrendIdea] = []
        for idea in scored:
            src = idea.source
            if source_counts.get(src, 0) < max_per_source:
                source_counts[src] = source_counts.get(src, 0) + 1
                diverse.append(idea)
                if len(diverse) >= max_results:
                    break
        return diverse

    def discover(
        self,
        niche: str = "",
        max_results: int = 10,
        use_cache: bool = True,
    ) -> list[TrendIdea]:
        niche = niche or self._niche
        cache_key = f"discovery:{niche}" if use_cache else None

        if use_cache and self._cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                self._logger.info("Returning %d cached ideas", len(cached))
                top = [TrendIdea(**item) for item in cached]
                return self._diversify(top, max_results)

        # Collect from all sources
        all_ideas: list[TrendIdea] = []
        for name, source in self._sources.items():
            try:
                self._logger.debug("Fetching from source: %s", name)
                ideas = source.fetch()
                self._logger.debug("Got %d ideas from %s", len(ideas), name)
                all_ideas.extend(ideas)
            except Exception as e:
                self._logger.warning("Source '%s' failed: %s", name, e)

        self._logger.info("Collected %d raw ideas from %d sources", len(all_ideas), len(self._sources))

        if not all_ideas:
            return []

        # Deduplicate
        unique = deduplicate_ideas(all_ideas)
        self._logger.info("After dedup: %d unique ideas", len(unique))

        # Score and rank
        scored = self._scorer.score_all(unique, niche=niche)

        top = self._diversify(scored, max_results)

        # Cache results (store full scored list, not just diverse slice)
        if use_cache and self._cache:
            self._cache.set(
                cache_key,
                [t.__dict__ for t in scored],
                ttl=1800,
            )

        return top
