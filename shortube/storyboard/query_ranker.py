from __future__ import annotations

from shortube.core.types import Scene
from shortube.storyboard.semantic_ranker import semantic_similarity


def rank_queries(scene: Scene) -> list[str]:
    scene.search_queries.sort(
        key=lambda q: _query_relevance(q, scene.visual_description),
        reverse=True,
    )
    return scene.search_queries


def _query_relevance(query: str, visual_desc: str) -> float:
    sem = semantic_similarity(query, visual_desc)
    if sem > 0.1:
        return sem
    query_words = set(query.lower().split())
    desc_words = set(visual_desc.lower().split())
    if not query_words:
        return 0.0
    overlap = len(query_words & desc_words)
    return overlap / len(query_words)
