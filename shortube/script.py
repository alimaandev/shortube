from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field, ValidationError

from shortube.config import get_settings
from shortube.llm import LLMError, create_llm
from shortube.types import Script

logger = logging.getLogger(__name__)

MAX_SPOKEN_SECONDS = 55.0
WORDS_PER_SECOND = 2.6  # ~156 wpm narrated speech
MIN_KEYWORD_DENSITY = 0.6


class ScriptOutput(BaseModel):
    hook: str
    points: list[str] = Field(default_factory=list)
    cta: str
    full_text: str
    keywords: list[str] = Field(default_factory=list)
    title: str = ""
    tags: list[str] = Field(default_factory=list)


_PROMPT = """You are a YouTube Shorts script writer for the niche: {niche}.

Given the topic "{topic}", write a complete YouTube Shorts script.

Requirements:
- Hook: 1 sentence that grabs attention (8-30 words)
- Points: exactly 3 short points (1-2 sentences each)
- CTA: 1 call-to-action sentence
- Title: A click-worthy title (max 60 chars)
- Keywords: 5-8 search keywords for stock video search
- Tags: 8-12 relevant hashtags (without the # symbol)
- Full text: the complete script as one paragraph (hook + points + cta)
- Keep language simple (Flesch-Kincaid grade ≤ 8)
- Write in third person, factual tone — no first-person stories
- Total script must be under 55 seconds when spoken (YouTube Shorts max is 60s)
- Naturally include EVERY keyword in the script text

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


def _clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"https?://\S+|www\.\S+", "", text)
    text = re.sub(r"[*_`#]{1,}", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _has_junk(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in ("lorem ipsum", "{topic}", "[insert", "placeholder", "……")
    ) or bool(re.search(r"https?://|www\.", text))


def _word_overlap(needle: str, haystack: str) -> float:
    a = set(re.findall(r"\b[a-z0-9']+\b", needle.lower()))
    b = set(re.findall(r"\b[a-z0-9']+\b", haystack.lower()))
    if not a:
        return 0.0
    return len(a & b) / len(a)


def score_keyword_density(keywords: list[str], text: str) -> float:
    """Fraction of script keywords that actually appear in the script text."""
    if not keywords:
        return 1.0
    found = 0
    for kw in keywords:
        if re.search(rf"\b{re.escape(kw.strip())}\b", text, re.IGNORECASE):
            found += 1
    return found / len(keywords)


def validate_script_output(validated: ScriptOutput, topic: str) -> list[str]:
    """Return a list of human-readable problems. Empty list = script is good."""
    errors: list[str] = []

    if not validated.hook:
        errors.append("hook is empty")
    elif len(validated.hook) < 8:
        errors.append("hook is too short (min 8 chars)")
    elif len(validated.hook) > 160:
        errors.append("hook is too long (max 160 chars)")
    if _has_junk(validated.hook):
        errors.append("hook contains markdown/URL/placeholder junk")

    if not validated.points:
        errors.append("points list is empty")
    elif not (2 <= len(validated.points) <= 4):
        errors.append(f"expected 3 points, got {len(validated.points)}")
    else:
        for i, p in enumerate(validated.points, 1):
            if not p.strip():
                errors.append(f"point {i} is empty")
            elif len(p.strip()) < 10:
                errors.append(f"point {i} is too short (min 10 chars)")
            elif len(p.strip()) > 260:
                errors.append(f"point {i} is too long (max 260 chars)")
            if _has_junk(p):
                errors.append(f"point {i} contains markdown/URL/placeholder junk")
        for i in range(len(validated.points)):
            for j in range(i + 1, len(validated.points)):
                if _word_overlap(validated.points[i], validated.points[j]) > 0.8:
                    errors.append(f"points {i+1} and {j+1} are near-duplicates")

    if not validated.cta:
        errors.append("cta is empty")
    elif len(validated.cta) < 6:
        errors.append("cta is too short (min 6 chars)")
    elif len(validated.cta) > 120:
        errors.append("cta is too long (max 120 chars)")
    if _has_junk(validated.cta):
        errors.append("cta contains markdown/URL/placeholder junk")

    if not validated.title:
        errors.append("title is empty")
    elif len(validated.title) > 60:
        errors.append("title exceeds 60 chars")
    if _has_junk(validated.title):
        errors.append("title contains markdown/URL/placeholder junk")

    if not validated.keywords:
        errors.append("keywords list is empty")
    elif not (3 <= len(validated.keywords) <= 8):
        errors.append(f"expected 3-8 keywords, got {len(validated.keywords)}")
    else:
        short = [k for k in validated.keywords if len(k.strip()) < 3]
        if short:
            errors.append(f"keywords too short: {', '.join(short[:3])}")

    if not validated.tags:
        errors.append("tags list is empty")
    elif not (4 <= len(validated.tags) <= 12):
        errors.append(f"expected 4-12 tags, got {len(validated.tags)}")

    if not validated.full_text:
        errors.append("full_text is empty")
    else:
        words = len(re.findall(r"\S+", validated.full_text))
        est = words / WORDS_PER_SECOND
        if est > MAX_SPOKEN_SECONDS:
            errors.append(
                f"script too long: ~{words} words ≈ {est:.0f}s spoken "
                f"(max {MAX_SPOKEN_SECONDS:.0f}s)"
            )
        if _word_overlap(validated.hook, validated.full_text) < 0.7:
            errors.append("full_text does not contain the hook")
        for i, p in enumerate(validated.points, 1):
            if _word_overlap(p, validated.full_text) < 0.6:
                errors.append(f"full_text does not contain point {i}")

    if validated.keywords and validated.full_text:
        density = score_keyword_density(validated.keywords, validated.full_text)
        if density < MIN_KEYWORD_DENSITY:
            missing = [
                k for k in validated.keywords
                if not re.search(rf"\b{re.escape(k.strip())}\b", validated.full_text, re.IGNORECASE)
            ]
            errors.append(
                f"keyword density {density:.0%} below {MIN_KEYWORD_DENSITY:.0%}; "
                f"naturally include: {', '.join(missing[:4])}"
            )

    if topic.strip() and _word_overlap(topic, validated.full_text) < 0.2:
        errors.append("script does not address the requested topic")

    return errors


def _to_script(validated: ScriptOutput, topic: str) -> Script:
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
    base_prompt = _PROMPT.format(niche=cfg.niche, topic=topic)
    hint = ""
    last_error = ""

    for attempt in range(3):
        try:
            prompt = base_prompt
            if hint:
                prompt += (
                    "\n\nPrevious attempt was rejected. Fix ALL of these issues:\n" + hint
                )
            raw = llm.generate_json(
                "You are a YouTube Shorts script writer. Output valid JSON only.",
                prompt,
                temperature=cfg.llm_temperature,
                max_tokens=1000,
            )
            validated = ScriptOutput(**raw)
            validated.hook = _clean_text(validated.hook)
            validated.points = [_clean_text(p) for p in validated.points]
            validated.cta = _clean_text(validated.cta)
            validated.full_text = _clean_text(validated.full_text)
            validated.title = _clean_text(validated.title)
            validated.keywords = [k.strip() for k in validated.keywords if k.strip()]
            validated.tags = [t.lstrip("#").strip() for t in validated.tags if t.strip()]

            errors = validate_script_output(validated, topic)
            if not errors:
                density = score_keyword_density(validated.keywords, validated.full_text)
                logger.info(
                    "Script generated for %s (density %.0f%%, ~%d words)",
                    topic[:60], density * 100,
                    len(re.findall(r"\S+", validated.full_text)),
                )
                return _to_script(validated, topic)

            hint = "\n".join(f"- {e}" for e in errors)
            logger.warning("Script attempt %d rejected: %s", attempt + 1, hint[:400])
        except LLMError as e:
            last_error = str(e)
            logger.warning("Script LLM attempt %d failed: %s", attempt + 1, e)
        except (ValidationError, TypeError, ValueError) as e:
            last_error = str(e)
            logger.warning("Script attempt %d failed: %s", attempt + 1, e)

    detail = hint or last_error
    if hint:
        raise ScriptError(
            f"Failed to generate a valid script after 3 attempts: {hint}"
        )
    raise ScriptError(
        f"Script generation failed: {detail or 'LLM returned no usable response'}"
    )