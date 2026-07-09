from __future__ import annotations

from typing import Any

from shortube.agents.base import BaseAgent
from shortube.config.settings import get_settings
from shortube.core.exceptions import AgentError
from shortube.shared.prompts import QUALITY_REVIEWER_PROMPT

_QUALITY_REVIEWER_SYSTEM = """You are a YouTube Shorts quality reviewer.
Review the given script and return JSON with the following keys:
- "hook_strength": int 1-10
- "clarity": int 1-10
- "pacing": int 1-10
- "engagement": int 1-10
- "call_to_action": int 1-10
- "overall_score": int 1-10
- "passed": bool (pass if overall_score >= {{ threshold }})
- "revision_notes": string — specific improvements needed
Output valid JSON only — no markdown, no code fences."""


class QualityReviewer(BaseAgent):
    @property
    def name(self) -> str:
        return "quality_reviewer"

    def _get_default_threshold(self) -> int:
        try:
            return get_settings().quality_pass_threshold
        except Exception:
            return 7

    def _compute_readability(self, text: str) -> dict:
        try:
            import textstat
            return {
                "flesch_kincaid": textstat.flesch_kincaid_grade(text),
                "flesch_reading": textstat.flesch_reading_ease(text),
                "syllable_count": textstat.syllable_count(text),
                "sentence_count": textstat.sentence_count(text),
            }
        except ImportError:
            return {}

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        script = context.get("script")
        if script is None:
            raise AgentError("QualityReviewer requires 'script' in context")

        readability = self._compute_readability(script.full_text)
        context["readability"] = readability

        fk_grade = readability.get("flesch_kincaid", 0)
        if fk_grade > 8:
            context["quality_notes"] = context.get("quality_notes", "") + (
                f" Readability too complex (Flesch-Kincaid grade {fk_grade:.1f}, target ≤ 8). Simplify language."
            )

        threshold = context.get("quality_threshold", self._get_default_threshold())
        script_text = (
            f"Hook: {script.hook}\n"
            f"Points: {' | '.join(script.points)}\n"
            f"CTA: {script.cta}\n"
            f"Title: {script.title}\n"
            f"Tags: {', '.join(script.tags)}\n"
            f"Readability: Flesch-Kincaid grade {fk_grade:.1f}"
        )
        system_prompt = _QUALITY_REVIEWER_SYSTEM.replace("{{ threshold }}", str(threshold))
        user_prompt = QUALITY_REVIEWER_PROMPT.render(script=script_text)
        result = self._call_llm(system_prompt, user_prompt)

        context["review"] = result
        context["quality_passed"] = result.get("passed", False)
        context["quality_score"] = result.get("overall_score", 0)

        if not result.get("passed", False):
            context["quality_notes"] = result.get("revision_notes", "")
            self._logger.warning(
                "Script quality score %d — below threshold. Notes: %s",
                result.get("overall_score", 0),
                result.get("revision_notes", ""),
            )

        return context
