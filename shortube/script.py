from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

from shortube.config import get_settings
from shortube.llm import LLMError, create_llm
from shortube.types import Script

logger = logging.getLogger(__name__)


class ScriptOutput(BaseModel):
    hook: str
    points: list[str] = Field(min_length=1)
    cta: str
    full_text: str
    keywords: list[str] = Field(default_factory=list)
    title: str = ""
    tags: list[str] = Field(default_factory=list)


_PROMPT = """You are a YouTube Shorts script writer for the niche: {niche}.

Given the topic "{topic}", write a complete YouTube Shorts script.

Requirements:
- Hook: 1 sentence that grabs attention
- Points: 3 short points (1-2 sentences each)
- CTA: 1 call-to-action sentence
- Title: A click-worthy title (max 60 chars)
- Keywords: 5-8 search keywords for stock video search
- Tags: 8-12 relevant hashtags (without the # symbol)
- Full text: the complete script as one paragraph (hook + points + cta)
- Keep language simple (Flesch-Kincaid grade ≤ 8)
- Write in third person, factual tone — no first-person stories
- Total script must be under 55 seconds when spoken (YouTube Shorts max is 60s)

Return ONLY valid JSON matching this schema:
{{
    "hook": "string",
    "points": ["string", "string", "string"],
    "cta": "string",
    "title": "string",
    "keywords": ["string"],
    "tags": ["string"],
    "full_text": "string"
}}"""


class ScriptError(Exception):
    pass


def generate_script(topic: str) -> Script:
    cfg = get_settings()
    if cfg.llm_provider == "ollama":
        api_key = ""
    else:
        api_key = cfg.groq_api_key if cfg.llm_provider == "groq" else cfg.openrouter_api_key
    llm = create_llm(
        provider=cfg.llm_provider,
        api_key=api_key,
        model=cfg.llm_model,
    )
    prompt = _PROMPT.format(niche=cfg.niche, topic=topic)

    for attempt in range(3):
        try:
            raw = llm.generate_json(
                "You are a YouTube Shorts script writer. Output valid JSON only.",
                prompt,
                temperature=0.7,
                max_tokens=1000,
            )
            validated = ScriptOutput(**raw)
            # Strip HTML tags from all text fields
            validated.full_text = re.sub(r"<[^>]+>", "", validated.full_text).strip()
            validated.hook = re.sub(r"<[^>]+>", "", validated.hook).strip()
            validated.points = [re.sub(r"<[^>]+>", "", p).strip() for p in validated.points]
            validated.cta = re.sub(r"<[^>]+>", "", validated.cta).strip()
            logger.info("Script generated for: %s", topic[:60])
            return Script(
                topic=topic,
                hook=validated.hook,
                points=validated.points,
                cta=validated.cta,
                full_text=validated.full_text,
                keywords=validated.keywords,
                title=validated.title,
                tags=validated.tags,
            )
        except Exception as e:
            logger.warning("Script attempt %d failed: %s", attempt + 1, e)

    raise ScriptError(f"Failed to generate valid script after 3 attempts")
