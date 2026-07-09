from __future__ import annotations

import logging
from typing import Any

from shortube.core.types import Scene
from shortube.shared.llm import LLMProvider

_QUERY_SYSTEM = """You generate search queries for stock footage.
Given a visual description, produce 3-5 search queries that would find matching footage.
Queries should be short (2-5 words), keyword-focused, and use terms stock sites understand.
Return JSON: {"queries": ["string", "string", "string"]}
Output valid JSON only — no markdown, no code fences."""

logger = logging.getLogger(__name__)


class QueryGenerator:
    def __init__(self, llm: LLMProvider | None = None):
        self._llm = llm

    def generate(self, scene: Scene) -> list[str]:
        if self._llm is None:
            return self._fallback_queries(scene)

        try:
            result = self._llm.generate_json(
                _QUERY_SYSTEM,
                f"Visual description: {scene.visual_description}",
                temperature=0.4,
                max_tokens=256,
            )
            queries = result.get("queries", [])
            return queries[:5] if queries else self._fallback_queries(scene)
        except Exception as e:
            logger.warning("Query generation failed: %s", e)
            return self._fallback_queries(scene)

    @staticmethod
    def _fallback_queries(scene: Scene) -> list[str]:
        words = scene.visual_description.split()[:5]
        return [" ".join(words)] if words else ["stock footage"]
