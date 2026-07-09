from __future__ import annotations

from typing import Any

from shortube.agents.base import BaseAgent
from shortube.shared.prompts import SEO_OPTIMIZER_PROMPT

_SEO_SYSTEM = """You are a YouTube SEO specialist.
Optimize the given script metadata for search and click-through.
Return JSON:
{
  "title": "string — under 60 chars, keyword-rich, clickable",
  "tags": ["string — mix broad + niche, max 10"],
  "description_hook": "string — first 2 lines of description"
}
Output valid JSON only — no markdown, no code fences."""


class SEOOptimizer(BaseAgent):
    @property
    def name(self) -> str:
        return "seo_optimizer"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        raw_script = context.get("raw_script") or {}
        script = context.get("script")

        if script is not None and hasattr(script, "title"):
            title = script.title
            tags = ", ".join(script.tags)
            desc = f"{script.hook} {' '.join(script.points)} {script.cta}"
        else:
            title = raw_script.get("title", context.get("topic", ""))
            tags = ", ".join(raw_script.get("tags", []))
            desc = raw_script.get("hook", "")

        user_prompt = SEO_OPTIMIZER_PROMPT.render(
            title=title, tags=tags, description=desc,
        )

        result = self._call_llm(_SEO_SYSTEM, user_prompt)

        if script is not None and hasattr(script, "title"):
            script.title = result.get("title", script.title)
            script.tags = result.get("tags", script.tags)
        if "raw_script" in context:
            context["raw_script"]["title"] = result.get("title", title)
            context["raw_script"]["tags"] = result.get("tags", raw_script.get("tags", []))
            context["raw_script"]["description_hook"] = result.get("description_hook", "")

        context["seo"] = result
        return context
