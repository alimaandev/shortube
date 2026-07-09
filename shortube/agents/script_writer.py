from __future__ import annotations

from typing import Any

from shortube.agents.base import BaseAgent
from shortube.config import NICHE
from shortube.core.types import Fact, Script

_SCRIPT_WRITER_SYSTEM = """You are a YouTube Shorts scriptwriter. Write concise, engaging scripts.
Output valid JSON only — no markdown, no code fences.

Schema:
{
  "hook": "string (1 sentence, max 15 words, attention-grabbing)",
  "points": ["string (1-2 sentences each, max 3 points)"],
  "cta": "string (1 sentence call to action)",
  "keywords": ["string (3-5 visual keywords for stock footage search)"],
  "title": "string (max 60 chars, SEO-optimized)",
  "tags": ["string (5-10 relevant tags)"]
}

Rules:
- Hook must be under 15 words.
- Exactly 3 points.
- Keywords: words Pexels understands (e.g. 'ocean waves', 'city skyline').
- Title: clickable, under 60 characters.
- Tags: mix broad + niche + #Shorts."""

_FACT_CHECK_SYSTEM = """You are a fact-checker for YouTube Shorts scripts.
Given a script and research facts, verify each claim in the script.
Return JSON:
{
  "verified_claims": ["string — claims that match research"],
  "unsupported_claims": ["string — claims not backed by research"],
  "contradicted_claims": ["string — claims that conflict with research"],
  "passed": bool (pass if no unsupported or contradicted claims)
}
Output valid JSON only — no markdown, no code fences."""


class ScriptWriter(BaseAgent):
    @property
    def name(self) -> str:
        return "script_writer"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        topic = context.get("topic", "")
        angle = context.get("angle", topic)
        audience = context.get("audience", "general")

        user_prompt = (
            f"Topic: {topic}\n"
            f"Angle: {angle}\n"
            f"Target audience: {audience}\n"
            f"Niche: {NICHE}\n"
            "Write a Shorts script for this topic. Return JSON only."
        )

        result = self._call_llm(_SCRIPT_WRITER_SYSTEM, user_prompt)

        full_text = " ".join([
            result.get("hook", ""),
            *result.get("points", []),
            result.get("cta", ""),
        ])

        script = Script(
            topic=topic,
            hook=result.get("hook", ""),
            points=result.get("points", []),
            cta=result.get("cta", ""),
            full_text=full_text,
            keywords=result.get("keywords", []),
            title=result.get("title", ""),
            tags=result.get("tags", []),
        )

        context["raw_script"] = result
        context["script"] = script

        # Fact-check against research
        research_note = context.get("research_note")
        if research_note and research_note.facts:
            facts_text = "\n".join(
                f"- {f.statement} (source: {f.source})" for f in research_note.facts
            )
            fc_prompt = (
                f"Script:\nHook: {script.hook}\nPoints: {' | '.join(script.points)}\nCTA: {script.cta}\n\n"
                f"Research facts:\n{facts_text}\n\n"
                "Check each claim against the research. Return JSON."
            )
            fc_result = self._call_llm(_FACT_CHECK_SYSTEM, fc_prompt, temperature=0.1)
            context["fact_check"] = fc_result
            if not fc_result.get("passed", True):
                self._logger.warning(
                    "Fact-check failed. Unsupported: %s. Contradicted: %s",
                    fc_result.get("unsupported_claims", []),
                    fc_result.get("contradicted_claims", []),
                )
                context["quality_notes"] = (
                    f"Fact-check issues: unsupported claims = {fc_result.get('unsupported_claims', [])}, "
                    f"contradicted = {fc_result.get('contradicted_claims', [])}"
                )

        return context
