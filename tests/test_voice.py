"""Voiceover generation: 60s-cap trimming and atomic file swaps."""

from __future__ import annotations

from pathlib import Path

import pytest

import shortube.voice as v


def test_cap_trim_drops_trailing_points(monkeypatch, settings, tmp_path):
    calls: list[str] = []

    async def fake_generate(text, audio_path, ts_path):
        calls.append(text)
        Path(audio_path).write_bytes(b"x" * 100)
        Path(ts_path).write_text(
            '{"timestamps": [{"word": "x", "start": 0, "end": 0.1}]}',
            encoding="utf-8",
        )
        return []

    def fake_probe(path):
        text = calls[-1] if calls else ""
        n = sum(1 for p in ["Point 1 text.", "Point 2 text.", "Point 3 text."] if p in text)
        return 40.0 if n <= 2 else 65.0

    monkeypatch.setattr(v, "_generate_with_timestamps", fake_generate)
    monkeypatch.setattr(v, "_probe_duration", fake_probe)

    out = tmp_path / "vo.mp3"
    v.generate_voiceover(
        "Hook.",
        ["Point 1 text.", "Point 2 text.", "Point 3 text."],
        "CTA.",
        str(out),
        max_duration=50.0,
    )
    assert len(calls) == 2
    assert "Point 3 text." not in calls[-1]
    assert out.exists()
    assert (tmp_path / "vo.timestamps.json").exists()


def test_failure_preserves_last_good_audio(monkeypatch, settings, tmp_path):
    async def failing_gen(text, audio_path, ts_path):
        raise RuntimeError("tts down")

    monkeypatch.setattr(v, "_generate_with_timestamps", failing_gen)
    out = tmp_path / "vo.mp3"
    out.write_bytes(b"GOOD AUDIO")
    with pytest.raises(v.VoiceError):
        v.generate_voiceover("Hook.", ["P."], "CTA.", str(out), max_duration=50.0)
    assert out.read_bytes() == b"GOOD AUDIO"
