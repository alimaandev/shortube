from __future__ import annotations

from typing import Any

from shortube.agents.base import BaseAgent
from shortube.core.exceptions import AgentError

_EDITOR_SYSTEM = """You are a YouTube Shorts script editor.
Improve the given script for conciseness, pacing, and engagement.
Keep the same structure (hook, points, cta) but make it tighter.
Return JSON:
{
  "hook": "string (max 15 words)",
  "points": ["string (1-2 sentences each)"],
  "cta": "string"
}
Output valid JSON only — no markdown, no code fences."""


class ScriptEditor(BaseAgent):
    @property
    def name(self) -> str:
        return "script_editor"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        raw_script = context.get("raw_script") or context.get("script")
        if raw_script is None:
            raise AgentError("ScriptEditor requires 'script' or 'raw_script' in context")

        if hasattr(raw_script, "hook"):
            script_text = (
                f"Hook: {raw_script.hook}\n"
                f"Points: {' | '.join(raw_script.points)}\n"
                f"CTA: {raw_script.cta}"
            )
        else:
            script_text = (
                f"Hook: {raw_script.get('hook', '')}\n"
                f"Points: {' | '.join(raw_script.get('points', []))}\n"
                f"CTA: {raw_script.get('cta', '')}"
            )

        revision_notes = context.get("revision_notes", "")
        prompt = script_text
        if revision_notes:
            prompt += f"\n\nRevision notes to address:\n{revision_notes}"

        result = self._call_llm(_EDITOR_SYSTEM, prompt, temperature=0.7)

        if "raw_script" in context:
            context["raw_script"].update(result)
        elif hasattr(context.get("script"), "hook"):
            script = context["script"]
            script.hook = result.get("hook", script.hook)
            script.points = result.get("points", script.points)
            script.cta = result.get("cta", script.cta)
            script.full_text = " ".join([script.hook] + script.points + [script.cta])

        context["edited"] = True
        return context
