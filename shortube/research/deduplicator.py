from __future__ import annotations

from difflib import SequenceMatcher
from typing import Sequence

from shortube.core.types import Fact


def deduplicate_facts(
    facts: Sequence[Fact],
    similarity_threshold: float = 0.75,
) -> list[Fact]:
    seen: list[str] = []
    unique: list[Fact] = []
    for fact in facts:
        normalized = fact.statement.lower().strip()
        if any(
            SequenceMatcher(None, normalized, seen_stmt).ratio() > similarity_threshold
            for seen_stmt in seen
        ):
            continue
        seen.append(normalized)
        unique.append(fact)
    return unique
