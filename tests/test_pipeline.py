"""Pipeline orchestration: assembly retry behavior (all stages mocked)."""

from __future__ import annotations

from pathlib import Path

import pytest

import shortube.pipeline as pl
from shortube.types import Scene, Script, Storyboard


def _fake_script(topic):
    return Script(
        topic=topic,
        hook="A hook sentence here",
        points=["Point one here"],
        cta="Follow for more",
        full_text="A hook sentence here Point one here Follow for more",
    )


def _fake_voice(hook, points, cta, path, max_duration=None):
    Path(path).write_bytes(b"x")
    Path(str(path).replace(".mp3", ".timestamps.json")).write_text(
        '{"timestamps": []}', encoding="utf-8"
    )


def _fake_storyboard(script, voice_path):
    s = Scene(
        index=0, start_time=0, end_time=4, narration=script.hook,
        visual_description="x", selected_media=[],
    )
    return Storyboard(script=script, scenes=[s], total_duration=4.0)


def _mock_pipeline(monkeypatch, tmp_path, assemble):
    monkeypatch.setattr(pl, "_check_dependencies", lambda: None)
    monkeypatch.setattr(pl, "_output_dir", lambda topic: tmp_path / "out")
    monkeypatch.setattr(pl, "generate_script", _fake_script)
    monkeypatch.setattr(pl, "generate_voiceover", _fake_voice)
    monkeypatch.setattr(pl, "generate_storyboard", _fake_storyboard)
    monkeypatch.setattr(pl, "assemble_video", assemble)


def test_assembly_retries_then_succeeds(monkeypatch, settings, tmp_path):
    calls = {"n": 0}

    def fake_assemble(storyboard, voice_path, video_path):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("render boom")
        Path(video_path).write_bytes(b"x" * 20_000)

    _mock_pipeline(monkeypatch, tmp_path, fake_assemble)
    result = pl.run_pipeline("retry test topic", dry_run=True)
    assert calls["n"] == 2
    assert Path(result["video"]).exists()


def test_assembly_total_failure_raises(monkeypatch, settings, tmp_path):
    calls = {"n": 0}

    def always_fail(storyboard, voice_path, video_path):
        calls["n"] += 1
        raise RuntimeError("always boom")

    _mock_pipeline(monkeypatch, tmp_path, always_fail)
    with pytest.raises(pl.PipelineError, match="failed after retry"):
        pl.run_pipeline("retry test topic 2", dry_run=True)
    assert calls["n"] == 2


def test_cancel_aborts_pipeline(monkeypatch, settings, tmp_path):
    import threading

    def cancelled_assemble(storyboard, voice_path, video_path):
        raise pl.PipelineCancelled("cancelled by user")

    _mock_pipeline(monkeypatch, tmp_path, cancelled_assemble)
    cancel_event = threading.Event()
    cancel_event.set()
    with pytest.raises(pl.PipelineCancelled):
        pl.run_pipeline(
            "cancel topic", dry_run=True,
            cancel_event=cancel_event,
        )
