"""Pipeline orchestration: assembly retry behavior (all stages mocked)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import shortube.pipeline as pl
from shortube.assemble import AssemblyError
from shortube.db import Database
from shortube.pipeline import CancelToken, PipelineOrchestrator, Stage, StageEvent
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
            raise AssemblyError("render boom")
        Path(video_path).write_bytes(b"x" * 20_000)

    _mock_pipeline(monkeypatch, tmp_path, fake_assemble)
    result = pl.run_pipeline("retry test topic", dry_run=True)
    assert calls["n"] == 2
    assert Path(result["video"]).exists()


def test_assembly_total_failure_raises(monkeypatch, settings, tmp_path):
    calls = {"n": 0}

    def always_fail(storyboard, voice_path, video_path):
        calls["n"] += 1
        raise AssemblyError("always boom")

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


def _success_assemble(storyboard, voice_path, video_path):
    Path(video_path).write_bytes(b"x" * 20_000)


def test_progress_reports_typed_stages(monkeypatch, settings, tmp_path):
    _mock_pipeline(monkeypatch, tmp_path, _success_assemble)
    events: list[StageEvent] = []
    pl.run_pipeline(
        "stages topic", dry_run=True, progress_callback=events.append
    )
    assert [e.stage for e in events] == [
        Stage.SCRIPT, Stage.VOICEOVER, Stage.STORYBOARD, Stage.ASSEMBLE,
    ]
    script_ev = events[0]
    assert script_ev.message == "Generating script..."
    assert script_ev.percent == 5
    assert events[-1].percent == 65


def test_orchestrator_cancel_token(monkeypatch, settings, tmp_path):
    _mock_pipeline(monkeypatch, tmp_path, _success_assemble)
    token = CancelToken()
    token.cancel()
    with pytest.raises(pl.PipelineCancelled):
        PipelineOrchestrator().run("cancel token topic", dry_run=True, cancel=token)


def test_resume_reuses_cached_chain(monkeypatch, settings, tmp_path):
    script = _fake_script("resume topic")
    storyboard = _fake_storyboard(script, "")
    voice_path = tmp_path / "voiceover.mp3"
    voice_path.write_bytes(b"x")
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"x" * 20_000)

    db = Database()
    tid = db.add_topic("resume topic", niche="test")
    vid = db.create_video(tid, privacy="private")
    db.update_video(
        vid,
        script_json=json.dumps(script.to_dict()),
        storyboard_json=json.dumps(storyboard.to_dict()),
        voiceover_path=str(voice_path),
        video_path=str(video_path),
        status="assembled",
    )

    calls = {"script": 0, "voice": 0, "storyboard": 0}
    _mock_pipeline(monkeypatch, tmp_path, _success_assemble)
    monkeypatch.setattr(pl, "generate_script",
                        lambda t: calls.update(script=1) or script)
    monkeypatch.setattr(pl, "generate_voiceover",
                        lambda *a, **k: calls.update(voice=1))
    monkeypatch.setattr(pl, "generate_storyboard",
                        lambda *a, **k: calls.update(storyboard=1) or storyboard)

    result = pl.run_pipeline("resume topic", dry_run=True, video_id=vid)
    assert result["script"] == "done (cached)"
    assert result["storyboard"] == "done (cached)"
    assert calls == {"script": 0, "voice": 0, "storyboard": 0}
    assert result["video"] == str(video_path)


def test_resume_regenerates_when_cache_incomplete(monkeypatch, settings, tmp_path):
    script = _fake_script("partial topic")
    storyboard = _fake_storyboard(script, "")
    db = Database()
    tid = db.add_topic("partial topic", niche="test")
    vid = db.create_video(tid, privacy="private")
    db.update_video(
        vid,
        script_json=json.dumps(script.to_dict()),
        storyboard_json=json.dumps(storyboard.to_dict()),
        status="storyboard_done",
    )

    calls = {"script": 0}
    _mock_pipeline(monkeypatch, tmp_path, _success_assemble)
    monkeypatch.setattr(pl, "generate_script",
                        lambda t: calls.update(script=1) or script)

    result = pl.run_pipeline("partial topic", dry_run=True, video_id=vid)
    assert calls["script"] == 1
    assert result["script"] == "done"
