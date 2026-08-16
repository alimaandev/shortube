from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

from shortube.remotion_bridge import render_video
from shortube.types import Storyboard

logger = logging.getLogger(__name__)


class AssemblyError(Exception):
    pass


def _load_timestamps(timestamp_path: str) -> list[dict]:
    ts_file = Path(timestamp_path)
    if not ts_file.exists():
        return []
    try:
        data = json.loads(ts_file.read_text(encoding="utf-8"))
        return data.get("timestamps", [])
    except Exception:
        return []


def _normalize_loudness(output_path: str) -> None:
    """Normalize audio to YouTube's -14 LUFS target. Non-fatal on failure."""
    if shutil.which("ffmpeg") is None:
        logger.warning("ffmpeg not found — skipping loudness normalization")
        return

    out = Path(output_path)
    norm = out.with_name(out.stem + "_loudnorm.mp4")
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(out),
                "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                str(norm),
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode == 0 and norm.exists() and norm.stat().st_size > 0:
            os.replace(norm, out)
            logger.info("Loudness normalized to -14 LUFS: %s", output_path)
        else:
            logger.warning(
                "Loudness normalization failed (exit %s): %s",
                result.returncode,
                (result.stderr or "")[-500:],
            )
    except Exception as e:
        logger.warning("Loudness normalization skipped: %s", e)
    finally:
        if norm.exists():
            norm.unlink(missing_ok=True)


def assemble_video(
    storyboard: Storyboard,
    voiceover_path: str,
    output_path: str,
) -> str:
    scenes = storyboard.scenes
    if not scenes:
        raise AssemblyError("Storyboard has no scenes")

    # All audio (voiceover, music ducking, SFX) is handled inside Remotion.
    ts_path = str(Path(voiceover_path).with_suffix(".timestamps.json"))
    word_ts = _load_timestamps(ts_path)

    # Render video via Remotion
    render_video(
        storyboard=storyboard,
        voiceover_path=voiceover_path,
        output_path=output_path,
        word_timestamps=word_ts,
    )

    _normalize_loudness(output_path)

    logger.info("Video assembled via Remotion: %s", output_path)
    return output_path
