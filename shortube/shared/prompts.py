from __future__ import annotations

from typing import Any


class PromptTemplate:
    def __init__(self, template: str, variables: list[str] | None = None):
        self.template = template
        self.variables = variables or []

    def render(self, **kwargs: Any) -> str:
        return self.template.format(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return {"template": self.template, "variables": self.variables}


# ── Script generation ──────────────────────────────────────────────────

SCRIPT_SYSTEM_PROMPT = PromptTemplate(
    template="""You are a YouTube Shorts scriptwriter. Write concise, engaging scripts.
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
)

# ── Topic discovery ────────────────────────────────────────────────────

DISCOVERY_SYSTEM_PROMPT = PromptTemplate(
    template="""You are a trend researcher for YouTube Shorts.
Your niche is {niche}.
Return a JSON object with a single key "topic" — a trending topic the audience would click on.
Output valid JSON only — no markdown, no code fences.
Example: {{"topic": "Why leaves change color in autumn"}}""",
    variables=["niche"],
)

# ── Agent prompts ──────────────────────────────────────────────────────

TOPIC_ANALYZER_PROMPT = PromptTemplate(
    template="""Analyze this topic for a YouTube Short: "{topic}"

Return JSON:
{{
  "angle": "string — unique angle or hook",
  "target_audience": "string — who would watch this",
  "difficulty": "easy|medium|hard",
  "estimated_interest": "high|medium|low"
}}""",
    variables=["topic"],
)

HOOK_GENERATOR_PROMPT = PromptTemplate(
    template="""Generate 5 attention-grabbing hooks for a YouTube Short about:
"{topic}"
Target audience: {audience}

Return JSON:
{{
  "hooks": ["string — each under 15 words, curiosity-driven"]
}}""",
    variables=["topic", "audience"],
)

OUTLINE_PROMPT = PromptTemplate(
    template="""Create a 3-point outline for a YouTube Short about "{topic}".
Keep each point to 1-2 punchy sentences.

Return JSON:
{{
  "points": ["string", "string", "string"],
  "suggested_visuals": ["string — per point, what to show"]
}}""",
    variables=["topic"],
)

SEO_OPTIMIZER_PROMPT = PromptTemplate(
    template="""Optimize this script for YouTube SEO:
Title: {title}
Tags: {tags}
Description: {description}

Return JSON:
{{
  "title": "string — under 60 chars, clickable, keyword-rich",
  "tags": ["string — mix broad + niche, max 10"],
  "description_hook": "string — first 2 lines for description"
}}""",
    variables=["title", "tags", "description"],
)

QUALITY_REVIEWER_PROMPT = PromptTemplate(
    template="""Review this YouTube Short script:
{script}

Score each criterion 1-10 and return JSON:
{{
  "hook_strength": int,
  "clarity": int,
  "pacing": int,
  "engagement": int,
  "call_to_action": int,
  "overall_score": int,
  "passed": bool,
  "revision_notes": "string — what to improve"
}}
Pass threshold: 6/10 overall.""",
    variables=["script"],
)


def get_prompt(name: str) -> PromptTemplate:
    registry = {
        "script_system": SCRIPT_SYSTEM_PROMPT,
        "discovery_system": DISCOVERY_SYSTEM_PROMPT,
        "topic_analyzer": TOPIC_ANALYZER_PROMPT,
        "hook_generator": HOOK_GENERATOR_PROMPT,
        "outline": OUTLINE_PROMPT,
        "seo_optimizer": SEO_OPTIMIZER_PROMPT,
        "quality_reviewer": QUALITY_REVIEWER_PROMPT,
    }
    tmpl = registry.get(name)
    if tmpl is None:
        raise ValueError(f"Unknown prompt template: {name}")
    return tmpl
