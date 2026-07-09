from __future__ import annotations

import logging

from shortube.core.types import Conflict, Fact
from shortube.shared.llm import LLMProvider

logger = logging.getLogger(__name__)

_CONFLICT_SYSTEM_PROMPT = """You are a fact-checking assistant. Compare two statements and determine if they conflict.
Return JSON: {"conflicts": bool, "description": "string explaining why or why not"}
Output valid JSON only — no markdown, no code fences."""


class FactChecker:
    def __init__(self, llm: LLMProvider | None = None):
        self._llm = llm

    def check_conflicts(self, facts: list[Fact]) -> list[Conflict]:
        conflicts: list[Conflict] = []
        if len(facts) < 2:
            return conflicts

        for i in range(len(facts)):
            for j in range(i + 1, len(facts)):
                if self._detect_conflict(facts[i], facts[j]):
                    conflicts.append(
                        Conflict(
                            fact_a=facts[i],
                            fact_b=facts[j],
                            description=f"Possible conflict detected",
                        )
                    )
        return conflicts

    def _detect_conflict(self, a: Fact, b: Fact) -> bool:
        if self._llm is None:
            return False
        user_prompt = (
            f"Statement A: {a.statement}\n"
            f"Statement B: {b.statement}\n"
            "Do these statements conflict with each other?"
        )
        try:
            result = self._llm.generate_json(
                _CONFLICT_SYSTEM_PROMPT, user_prompt,
                temperature=0.1, max_tokens=256,
            )
            return bool(result.get("conflicts", False))
        except Exception as e:
            logger.warning("Conflict detection failed: %s", e)
            return False
