from __future__ import annotations

from typing import Any

from shortube.agents.base import BaseAgent
from shortube.shared.prompts import HOOK_GENERATOR_PROMPT

_HOOK_SYSTEM = """You are a YouTube Shorts hook specialist.
Generate 5 attention-grabbing hooks for the given topic.
Each hook must be under 15 words and create curiosity.
Return JSON: {"hooks": ["string", "string", "string", "string", "string"]}
Output valid JSON only — no markdown, no code fences."""

_SCORE_SYSTEM = """Rate this YouTube Shorts hook on a scale of 1-10.
Criteria:
- curiosity (3 pts): does it make you need to know more?
- specificity (3 pts): is it concrete and specific, not generic?
- surprise (2 pts): does it subvert expectations?
- brevity (2 pts): is it under 10 words?

Return JSON: {"score": int, "reason": "string"}
Output valid JSON only — no markdown, no code fences."""


class HookGenerator(BaseAgent):
    @property
    def name(self) -> str:
        return "hook_generator"

    def _score_hook(self, hook: str, topic: str, audience: str) -> int:
        try:
            result = self._call_llm(
                _SCORE_SYSTEM,
                f"Hook: {hook}\nTopic: {topic}\nAudience: {audience}",
                temperature=0.1,
            )
            return int(result.get("score", 5))
        except Exception:
            return 5

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        topic = context.get("topic", "")
        audience = context.get("audience", "general")

        user_prompt = HOOK_GENERATOR_PROMPT.render(topic=topic, audience=audience)
        result = self._call_llm(_HOOK_SYSTEM, user_prompt)

        hooks = result.get("hooks", [])

        if hooks:
            scored: list[tuple[int, str]] = [
                (self._score_hook(h, topic, audience), h) for h in hooks
            ]
            scored.sort(reverse=True)
            best_hook = scored[0][1]
        else:
            best_hook = ""

        context["hook_candidates"] = hooks
        context["hook"] = best_hook
        return context
