"""Quality presets for video generation.

Each preset tunes render speed vs. output quality: fps, Remotion
concurrency, H.264 CRF and the loudness-pass audio bitrate. The preset
name is stored in settings (`QUALITY`) and used by the Remotion bridge
and the audio normalization pass.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class QualityPreset:
    fps: int
    concurrency: int  # 0 = let Remotion decide (auto)
    crf: int  # lower = higher quality / bigger file (H.264)
    audio_bitrate: str  # ffmpeg -b:a value for the loudnorm pass
    label: str


QUALITY_PRESETS: dict[str, QualityPreset] = {
    "fast": QualityPreset(
        fps=24, concurrency=2, crf=22, audio_bitrate="160k",
        label="Fast (draft, quick renders)",
    ),
    "standard": QualityPreset(
        fps=30, concurrency=0, crf=18, audio_bitrate="192k",
        label="Standard (balanced quality/speed)",
    ),
    "pro": QualityPreset(
        fps=30, concurrency=max(2, (os.cpu_count() or 4) // 2),
        crf=14, audio_bitrate="256k",
        label="Pro (best quality, slower renders)",
    ),
}

DEFAULT_QUALITY = "standard"


def resolve_preset(quality: str) -> QualityPreset:
    """Return the preset for a name, falling back to standard."""
    key = (quality or "").strip().lower()
    return QUALITY_PRESETS.get(key, QUALITY_PRESETS[DEFAULT_QUALITY])
