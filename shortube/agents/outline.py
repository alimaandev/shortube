from __future__ import annotations

from typing import Any

from shortube.agents.base import BaseAgent
from shortube.shared.prompts import OUTLINE_PROMPT

_OUTLINE_SYSTEM = """You are a YouTube Shorts outline creator.
Given a topic and research, create a structured 3-point outline.
Return JSON:
{
  "points": ["string — 1-2 punchy sentences each"],
  "suggested_visuals": ["string — what to show visually per point"]
}
Output valid JSON only — no markdown, no code fences."""


class OutlineAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "outline"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        topic = context.get("topic", "")
        research = context.get("research_note", None)
        research_summary = research.summary if research else ""

        user_prompt = OUTLINE_PROMPT.render(topic=topic)
        if research_summary:
            user_prompt += f"\n\nResearch summary:\n{research_summary}"

        result = self._call_llm(_OUTLINE_SYSTEM, user_prompt)
        context["outline_points"] = result.get("points", [])
        context["suggested_visuals"] = result.get("suggested_visuals", [])
        return context
