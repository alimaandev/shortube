from __future__ import annotations

from difflib import SequenceMatcher
from typing import Sequence

from shortube.core.types import TrendIdea


def deduplicate_ideas(
    ideas: Sequence[TrendIdea],
    similarity_threshold: float = 0.7,
) -> list[TrendIdea]:
    seen_titles: list[str] = []
    unique: list[TrendIdea] = []
    for idea in ideas:
        normalized = idea.title.lower().strip()
        if any(
            SequenceMatcher(None, normalized, seen).ratio() > similarity_threshold
            for seen in seen_titles
        ):
            continue
        seen_titles.append(normalized)
        unique.append(idea)
    return unique
