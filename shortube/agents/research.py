from __future__ import annotations

from typing import Any

from shortube.agents.base import BaseAgent
from shortube.core.interfaces import ResearchEngine as ResearchEngineInterface
from shortube.shared.llm import LLMProvider

_RESEARCH_SYSTEM = """You are a research coordinator. Your job is to direct research on a topic.
Instruct the research engine on what to look for.
Return JSON: {"research_direction": "string — what specific aspects to research"}
Output valid JSON only — no markdown, no code fences."""


class ResearchAgent(BaseAgent):
    def __init__(self, llm: LLMProvider, research_engine: ResearchEngineInterface, config=None):
        super().__init__(llm, config)
        self._research_engine = research_engine

    @property
    def name(self) -> str:
        return "research"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        topic = context.get("topic", "")
        self._logger.info("Researching topic: %s", topic)

        research_note = self._research_engine.research(topic)
        context["research_note"] = research_note

        if research_note.facts:
            self._logger.info(
                "Found %d facts, %d conflicts from %d sources",
                len(research_note.facts),
                len(research_note.conflicts),
                len(research_note.sources),
            )
        else:
            self._logger.warning("No research data found for topic")

        return context
