"""End-to-end smoke: real Remotion render through the real Python bridge.

This is the boundary proof for the whole render chain
(Python props JSON -> Remotion TSX -> ffmpeg loudnorm).

Gated by SHORTUBE_E2E=1 so routine `pytest` runs stay offline and fast;
requires Node.js and a prepared remotion project (npm install done).
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

pytestmark = [pytest.mark.e2e]

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REAL_REMOTION = PROJECT_ROOT / "remotion"


def _make_test_image(path: Path, size=(360, 640)) -> Path:
    img = Image.new("RGB", size, (30, 90, 180))
    draw = ImageDraw.Draw(img)
    draw.rectangle((40, 200, 320, 440), fill=(180, 60, 40))
    draw.text((60, 300), "SCENE", fill=(255, 255, 255))
    img.save(path, "JPEG", quality=85)
    return path


def _synthesize_voice(path: Path) -> list[dict]:
    """5s of silent audio (pydub; no ffmpeg needed) plus word timestamps."""
    from pydub import AudioSegment

    silence = AudioSegment.silent(duration=5000, frame_rate=24000)
    silence.export(str(path), format="wav")
    words = ["Cats", "always", "land", "on", "their", "feet", "righting", "reflex"]
    timestamps = []
    for i, w in enumerate(words):
        start = round(i * (4.8 / len(words)), 3)
        timestamps.append({"word": w, "start": start, "end": round(start + 0.4, 3)})
    return timestamps


@pytest.fixture
def render_settings(tmp_path, monkeypatch):
    """Settings for a small, fast real render in an isolated work dir."""
    from shortube.config import Settings, reset_settings

    reset_settings()
    orig_init = Settings.__init__

    def patched_init(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        self.base_dir = tmp_path
        self.remotion_project_dir = str(REAL_REMOTION)
        self.quality = "fast"
        self.video_width = 360
        self.video_height = 640
        self.video_fps = 24
        self.bumper_duration = 0.75
        self.transition_duration = 0.2
        self.template = ""
        self.sfx_enabled = False
        self.background_music_path = ""
        self.remotion_concurrency = 2

    monkeypatch.setattr(Settings, "__init__", patched_init)
    monkeypatch.setattr("shortube.config.get_settings", lambda: Settings())
    yield Settings()
    reset_settings()


def _require_render_environment():
    if os.environ.get("SHORTUBE_E2E") != "1":
        pytest.skip("set SHORTUBE_E2E=1 to run the real Remotion render smoke test")
    if shutil.which("npx") is None:
        pytest.skip("npx not found — Node.js is required for the render smoke test")
    if not (REAL_REMOTION / "package.json").exists():
        pytest.skip(f"Remotion project missing: {REAL_REMOTION}")


def test_render_smoke(render_settings, tmp_path):
    _require_render_environment()

    from shortube.assemble import assemble_video
    from shortube.types import MediaAsset, Scene, Script, Storyboard

    media = _make_test_image(tmp_path / "scene_a.jpg")
    script = Script(
        topic="Cats Always Land on Their Feet",
        hook="Cats always land on their feet thanks to a righting reflex",
        points=["The righting reflex kicks in at just 3 weeks old."],
        cta="Follow for more animal facts",
        full_text=(
            "Cats always land on their feet. "
            "The righting reflex kicks in at just 3 weeks old. "
            "Follow for more animal facts"
        ),
        keywords=["cats", "reflex"],
        tags=["shorts", "animals", "cats"],
        title="Why Cats Always Land on Their Feet",
    )
    scenes = [
        Scene(
            index=0, start_time=0.0, end_time=2.5, narration=script.hook,
            visual_description="cat mid-air",
            selected_media=[
                MediaAsset(
                    url="", type="image", provider="test",
                    width=360, height=640, local_path=str(media),
                )
            ],
        ),
        Scene(
            index=1, start_time=2.5, end_time=5.0, narration=script.points[0],
            visual_description="kitten close-up",
            selected_media=[
                MediaAsset(
                    url="", type="image", provider="test",
                    width=360, height=640, local_path=str(media),
                )
            ],
        ),
    ]
    storyboard = Storyboard(script=script, scenes=scenes, total_duration=5.0)

    voice = tmp_path / "voiceover.wav"
    timestamps = _synthesize_voice(voice)
    voice.with_suffix(".timestamps.json").write_text(
        json.dumps({"timestamps": timestamps}), encoding="utf-8"
    )

    output = tmp_path / "final.mp4"
    assemble_video(storyboard, str(voice), str(output))

    assert output.exists(), "render produced no output file"
    assert output.stat().st_size > 10_000, "output file suspiciously small"

    # The Python frame formula must match the TS composition — a mismatch
    # surfaces here as a Remotion error or a wrong-length video.
    if shutil.which("ffmpeg"):
        from pydub import AudioSegment

        audio = AudioSegment.from_file(str(output))
        assert 4.0 <= audio.duration_seconds <= 8.0, audio.duration_seconds