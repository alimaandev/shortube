from __future__ import annotations

import logging
from typing import Sequence

from shortube.core.types import TrendIdea
from shortube.shared.llm import LLMProvider

logger = logging.getLogger(__name__)

SOURCE_WEIGHTS = {
    "hacker_news": 0.15,
    "reddit": 0.10,
    "youtube": 0.20,
    "rss": 0.08,
    "web": 0.05,
    "lobsters": 0.12,
    "github": 0.15,
    "devto": 0.10,
    "hackaday": 0.08,
    "wikipedia": 0.12,
    "arstechnica": 0.12,
    "theverge": 0.10,
}

MOMENTUM_BONUS = {
    "rising": 30.0,
    "stable": 10.0,
    "declining": 0.0,
}


class Scorer:
    def __init__(self, llm: LLMProvider | None = None):
        self._llm = llm

    def score_all(
        self,
        ideas: Sequence[TrendIdea],
        niche: str = "",
    ) -> list[TrendIdea]:
        for idea in ideas:
            idea.score = self._score_single(idea, niche)
        ideas_sorted = sorted(ideas, key=lambda x: x.score, reverse=True)
        return ideas_sorted

    def _score_single(self, idea: TrendIdea, niche: str) -> float:
        score = 0.0

        # Source authority component (0–20)
        score += SOURCE_WEIGHTS.get(idea.source, 0.05) * 100

        # Momentum component (0–30)
        score += MOMENTUM_BONUS.get(idea.momentum, 5.0)

        # Base score from source (0–10 from the source itself)
        score += idea.score

        # Niche relevance boost (0–40 via LLM)
        if self._llm and niche:
            relevance = self._estimate_relevance(idea.title, niche)
            score += relevance * 40.0

        return score

    def _estimate_relevance(self, title: str, niche: str) -> float:
        try:
            result = self._llm.generate_json(
                "You evaluate topic relevance. Return JSON: {\"relevance\": float 0.0-1.0}",
                f"Topic: {title}\nNiche: {niche}\nHow relevant is this topic to the niche?",
                temperature=0.1,
                max_tokens=100,
            )
            return float(result.get("relevance", 0.5))
        except Exception as e:
            logger.warning("Relevance check failed: %s", e)
            return 0.5
