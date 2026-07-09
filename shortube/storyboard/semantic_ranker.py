from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_MODEL = None


def _get_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    try:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    except Exception as e:
        logger.warning("sentence-transformers not available: %s — falling back to word overlap", e)
        _MODEL = None
    return _MODEL


def semantic_similarity(text_a: str, text_b: str) -> float:
    model = _get_model()
    if model is None:
        return 0.0
    try:
        emb = model.encode([text_a, text_b])
        import numpy as np
        sim = float(np.dot(emb[0], emb[1]) / (np.linalg.norm(emb[0]) * np.linalg.norm(emb[1])))
        return max(0.0, sim)
    except Exception as e:
        logger.warning("Semantic similarity failed: %s", e)
        return 0.0


def rank_assets_by_relevance(
    assets: list,
    visual_description: str,
) -> list:
    if not assets or not visual_description:
        return assets
    scored = []
    for asset in assets:
        desc = getattr(asset, "description", "") or getattr(asset, "title", "") or ""
        score = semantic_similarity(visual_description[:200], desc[:200])
        scored.append((score, asset))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in scored]