"""Script generation: validation gates, retry-with-hints, error surfacing."""

from __future__ import annotations

import pytest

from shortube.llm import LLMError
from shortube.script import (
    ScriptError,
    ScriptOutput,
    generate_script,
    score_keyword_density,
    validate_script_output,
)

GOOD = ScriptOutput(
    hook="Cats always land on their feet thanks to a righting reflex",
    points=[
        "The righting reflex develops when kittens reach just 3 weeks old.",
        "Cats use their inner ear balance system to detect which way is up.",
        "The tail rotates in the opposite direction to keep the body aligned.",
    ],
    cta="Follow for more amazing animal facts every day",
    title="Why Cats Always Land on Their Feet",
    keywords=["cats", "righting reflex", "kittens", "balance", "falling", "animals"],
    tags=["shorts", "animals", "cats", "science", "facts", "pet", "education", "viral"],
    full_text=(
        "Cats always land on their feet thanks to a righting reflex. "
        "The righting reflex develops when kittens reach just 3 weeks old. "
        "Cats use their inner ear balance system to detect which way is up. "
        "The tail rotates in the opposite direction to keep the body aligned. "
        "Follow for more amazing animal facts every day"
    ),
)


def test_good_script_passes():
    assert validate_script_output(GOOD, "Why cats land on their feet") == []


def test_empty_script_reports_all_errors():
    bad = ScriptOutput(
        hook="", points=[], cta="", full_text="", title="", keywords=[], tags=[]
    )
    errs = validate_script_output(bad, "topic")
    for msg in (
        "hook is empty",
        "points list is empty",
        "cta is empty",
        "full_text is empty",
        "title is empty",
        "tags list is empty",
        "keywords list is empty",
    ):
        assert msg in errs, f"missing error: {msg}"


def test_near_duplicate_points_detected():
    dup = ScriptOutput(
        hook="This is a perfectly good hook sentence",
        points=[
            "The same point repeated twice in a row.",
            "The same point repeated twice in a row.",
        ],
        cta="Great cta right here",
        full_text=(
            "This is a perfectly good hook sentence. "
            "The same point repeated twice in a row. Great cta right here"
        ),
        keywords=["good", "point", "hook"],
        tags=["a", "b", "c", "d"],
        title="A fine title",
    )
    errs = validate_script_output(dup, "topic")
    assert any("near-duplicates" in e for e in errs), errs


def test_duration_budget_rejects_long_script():
    long_text = " ".join(["word"] * 200)
    longs = ScriptOutput(
        hook="Good hook sentence here",
        points=["A point that is quite fine to see", "Another point that is fine to see"],
        cta="Good cta here",
        full_text=long_text,
        keywords=["word", "point", "hook"],
        tags=["a", "b", "c", "d"],
        title="Title here",
    )
    errs = validate_script_output(longs, "topic")
    assert any("too long" in e and "spoken" in e for e in errs), errs


def test_partial_keyword_density_scores_proportionally():
    # Whole-word matching: "falling" and "animals" (text says "animal facts")
    # don't match GOOD.full_text → 4/6.
    assert score_keyword_density(GOOD.keywords, GOOD.full_text) == pytest.approx(4 / 6)


def test_density_gate_accepts_covered_keywords():
    dense = ScriptOutput(
        hook="Cats fall and always land on their feet with a reflex",
        points=[
            "This point mentions kittens and falling cats together.",
            "Another point about the righting reflex and balance here.",
            "A third point about animals and how they land safely.",
        ],
        cta="Follow for more animal facts",
        full_text=(
            "Cats fall and always land on their feet with a reflex. "
            "This point mentions kittens and falling cats together. "
            "Another point about the righting reflex and balance here. "
            "A third point about animals and how they land safely. "
            "Follow for more animal facts"
        ),
        keywords=["cats", "kittens", "righting reflex", "falling", "balance", "animals"],
        tags=["a", "b", "c", "d", "e", "f"],
        title="Cats",
    )
    assert score_keyword_density(dense.keywords, dense.full_text) == 1.0
    assert validate_script_output(dense, "cats landing on their feet") == []


def test_density_gate_rejects_missing_keywords():
    thin = ScriptOutput(**{**GOOD.model_dump(), "keywords": ["cats", "quantum physics", "basket weaving"]})
    errs = validate_script_output(thin, "topic")
    assert any("keyword density" in e and "quantum physics" in e for e in errs), errs


class _FakeGoodLLM:
    """Fails validation once, then produces a perfect script."""

    def __init__(self) -> None:
        self.calls = 0
        self.prompts: list[str] = []

    def generate_json(self, system, prompt, temperature, max_tokens):
        self.calls += 1
        self.prompts.append(prompt)
        if self.calls == 1:
            return {
                "hook": "x", "points": [], "cta": "", "full_text": "x",
                "title": "", "keywords": [], "tags": [],
            }
        return GOOD.model_dump()


def test_generate_script_retries_with_fix_hints(monkeypatch, settings):
    fake = _FakeGoodLLM()
    monkeypatch.setattr("shortube.script.create_llm", lambda **kw: fake)
    out = generate_script("Why cats land on their feet")
    assert fake.calls == 2
    assert "Previous attempt was rejected" in fake.prompts[1]
    assert out.title == GOOD.title
    assert len(out.points) == 3


def test_generate_script_raises_after_exhausting_attempts(monkeypatch, settings):
    class _BadLLM:
        def generate_json(self, *a, **kw):
            return {
                "hook": "x", "points": [], "cta": "", "full_text": "x",
                "title": "", "keywords": [], "tags": [],
            }

    monkeypatch.setattr("shortube.script.create_llm", lambda **kw: _BadLLM())
    with pytest.raises(ScriptError) as exc:
        generate_script("topic")
    assert "hook" in str(exc.value)


def test_generate_script_surfaces_llm_failure_cause(monkeypatch, settings):
    def boom(*a, **kw):
        raise LLMError("Ollama API call failed: connection refused")

    monkeypatch.setattr("shortube.script.create_llm", boom)
    # create_llm failures surface directly (config-level errors aren't
    # retried); mid-generation failures wrap into ScriptError.
    with pytest.raises(LLMError) as exc:
        generate_script("topic")
    assert "connection refused" in str(exc.value)
