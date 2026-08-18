"""Remotion bridge: input JSON contract and frame-count math."""

from __future__ import annotations

import json
from pathlib import Path

from shortube.remotion_bridge import _prepare_input_json, composition_frames
from shortube.types import Scene, Script, Storyboard


def _storyboard() -> Storyboard:
    script = Script(
        topic="Why Cats Always Land on Their Feet",
        hook="Scientists say cats always land on their feet",
        points=[
            "The righting reflex kicks in at just 3 weeks old.",
            "They use their eyes and inner ear to find up.",
        ],
        cta="Follow for more animal facts",
        full_text=(
            "Scientists say cats always land on their feet. "
            "The righting reflex kicks in at just 3 weeks old. "
            "Follow for more animal facts"
        ),
    )
    scenes = [
        Scene(
            index=0, start_time=0.0, end_time=4.0,
            narration=script.hook, visual_description="cat mid-air twist",
            selected_media=[],
        ),
        Scene(
            index=1, start_time=4.0, end_time=8.0,
            narration=script.points[0], visual_description="kitten reflex close-up",
            selected_media=[],
        ),
    ]
    return Storyboard(script=script, scenes=scenes, total_duration=8.0)


def test_prepare_input_json_contract(settings, monkeypatch, tmp_path):
    import json as _json

    s = settings
    s.template = "clean"
    monkeypatch.setattr("shortube.config.get_settings", lambda: s)
    # remotion_bridge and template_loader hold module-level import bindings.
    monkeypatch.setattr("shortube.remotion_bridge.get_settings", lambda: s)
    monkeypatch.setattr("shortube.template_loader.get_settings", lambda: s)

    # The template loader resolves templates relative to base_dir, which is
    # the isolated tmp dir — provide a minimal clean.json there.
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "clean.json").write_text(
        _json.dumps({"id": "clean", "transition": "slide", "accent": "#1976d2"}),
        encoding="utf-8",
    )

    input_file = _prepare_input_json(
        _storyboard(),
        "voiceover.mp3",
        str(tmp_path / "out.mp4"),
        [{"word": "cats", "start": 0.1, "end": 0.4}],
        tmp_path / "remotion",
        "smoketest",
    )
    data = json.loads(Path(input_file).read_text(encoding="utf-8"))
    t = data["templateData"]
    assert t["id"] == "clean"
    assert t["transition"] == "slide"
    assert data["captionFontSize"] == 48
    assert data["scenes"][0]["index"] == 0
    assert data["script"]["topic"].startswith("Why Cats")


def test_composition_frames_no_transitions_for_two_scenes():
    sb_ = _storyboard()
    assert composition_frames(sb_.scenes, fps=30, bumper_frames=45, transition_frames=9) == (
        2 * 45 + 120 + 120
    )


def test_composition_frames_with_transitions():
    sb_ = _storyboard()
    sb_.scenes.append(
        Scene(
            index=2, start_time=8.0, end_time=12.0,
            narration="third", visual_description="x", selected_media=[],
        )
    )
    assert composition_frames(sb_.scenes, fps=30, bumper_frames=45, transition_frames=9) == (
        2 * 45 + 3 * 120 + 1 * 9
    )