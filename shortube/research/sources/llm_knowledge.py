from __future__ import annotations

import logging

from shortube.core.types import Fact
from shortube.shared.llm import LLMProvider

logger = logging.getLogger(__name__)

_KNOWLEDGE_SYSTEM_PROMPT = """You are a research assistant. Given a topic, provide key facts.
Return a JSON array of objects with keys: "statement", "confidence" (0.0-1.0).
Each statement should be a single factual claim.
Output valid JSON only — no markdown, no code fences.
Example: [{"statement": "The Earth orbits the Sun", "confidence": 0.95}]"""


class LLMKnowledgeSource:
    name = "llm_knowledge"

    def __init__(self, llm: LLMProvider):
        self._llm = llm

    def fetch(self, topic: str, max_results: int = 5) -> list[Fact]:
        user_prompt = (
            f"Topic: {topic}\n"
            f"Provide up to {max_results} key facts about this topic. "
            "Return JSON array only."
        )
        try:
            result = self._llm.generate_json(
                _KNOWLEDGE_SYSTEM_PROMPT, user_prompt,
                temperature=0.3, max_tokens=1024,
            )
            if isinstance(result, list):
                return [
                    Fact(
                        statement=item.get("statement", ""),
                        source="LLM knowledge",
                        confidence=float(item.get("confidence", 0.5)),
                    )
                    for item in result
                    if item.get("statement")
                ]
            return []
        except Exception as e:
            logger.warning("LLM knowledge fetch failed: %s", e)
            return []
