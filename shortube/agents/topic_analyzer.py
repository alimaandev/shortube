from __future__ import annotations

from typing import Any

from shortube.agents.base import BaseAgent
from shortube.shared.prompts import TOPIC_ANALYZER_PROMPT

_TOPIC_ANALYZER_SYSTEM = """You are a YouTube Shorts topic analyst.
Analyze the given topic and return JSON with the following keys:
- "angle": a unique, clickable angle for the video
- "target_audience": who would watch this
- "difficulty": "easy", "medium", or "hard"
- "estimated_interest": "high", "medium", or "low"
Output valid JSON only — no markdown, no code fences."""


class TopicAnalyzer(BaseAgent):
    @property
    def name(self) -> str:
        return "topic_analyzer"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        topic = context.get("topic", "")
        user_prompt = TOPIC_ANALYZER_PROMPT.render(topic=topic)
        result = self._call_llm(_TOPIC_ANALYZER_SYSTEM, user_prompt)
        context["analysis"] = result
        context["angle"] = result.get("angle", topic)
        context["audience"] = result.get("target_audience", "general")
        context["difficulty"] = result.get("difficulty", "medium")
        return context
