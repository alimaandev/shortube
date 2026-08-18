"""Trend discovery: refinement behavior and the discovery flow."""

from __future__ import annotations

from shortube.discover import discover, refine_topics
from shortube.llm import LLMError
from shortube.types import TrendIdea

RAW = [TrendIdea(title="NASA Finds New Planet", source="rss", score=3.0)]


def test_refine_falls_back_to_raw_on_llm_failure(monkeypatch):
    def boom(*a, **kw):
        raise LLMError("down")

    monkeypatch.setattr("shortube.discover.create_llm", boom)
    assert refine_topics(RAW, "space", 5) == RAW


class _GoodLLM:
    def generate_json(self, system, prompt, temperature, max_tokens):
        return {
            "topics": [
                {"title": "NASA finds a new exoplanet", "reason": "space news performs well"},
                {"title": "Space junk danger", "reason": "timely"},
            ]
        }


def test_refine_happy_path_maps_titles_and_scores(monkeypatch):
    monkeypatch.setattr("shortube.discover.create_llm", lambda **kw: _GoodLLM())
    out = refine_topics(RAW, "space", 5)
    assert out[0].title == "NASA finds a new exoplanet"
    assert out[0].source == "rss"  # inherits source from the closest original
    assert out[1].source == "llm"
    assert out[1].score == 9.0


def test_refine_returns_raw_when_llm_returns_junk(monkeypatch):
    class _JunkLLM:
        def generate_json(self, *a, **kw):
            return {}

    monkeypatch.setattr("shortube.discover.create_llm", lambda **kw: _JunkLLM())
    assert refine_topics(RAW, "space", 5) == RAW


def test_discover_flow_with_fake_source(monkeypatch):
    def fake_hn():
        return [
            TrendIdea(title="Real Science Headline from HN", source="hackernews", score=9.0)
        ]

    monkeypatch.setattr("shortube.discover._SOURCES", {"hackernews": fake_hn})
    monkeypatch.setattr(
        "shortube.discover.refine_topics",
        lambda ideas, niche, max_results: ideas[:max_results],
    )
    out = discover("science", 5)
    assert out
    assert out[0].title == "Real Science Headline from HN"
