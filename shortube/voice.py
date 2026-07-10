from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import edge_tts

from shortube.config import get_settings

logger = logging.getLogger(__name__)


class VoiceError(Exception):
    """Raised when voiceover generation fails."""


def build_text(hook: str, points: list[str], cta: str) -> str:
    """Build natural speech text from script components without SSML.

    Uses punctuation and line breaks to create natural pacing.
    """
    parts: list[str] = [hook]
    for pt in points:
        parts.append(pt)
    parts.append(cta)
    return "\n\n".join(parts)


def _speed_to_streak(speed: float) -> str:
    return f"+{int((speed - 1.0) * 100)}%"


def _run_async(coro):
    """Run a coroutine safely, handling existing event loops."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)


def _verify_audio_file(path: str) -> None:
    p = Path(path)
    if not p.exists():
        raise VoiceError(f"Voiceover file was not created: {path}")
    size = p.stat().st_size
    if size == 0:
        raise VoiceError(f"Voiceover file is empty: {path}")
    logger.debug("Audio file verified: %s (%d bytes)", path, size)


async def _generate_with_timestamps(
    text: str,
    output_path: str,
    timestamps_path: str,
) -> list[dict]:
    """Generate TTS audio and word-level timestamps using edge-tts.

    edge-tts returns WordBoundary events with:
      - text: the word or boundary marker
      - offset: time offset in 100-nanosecond units
      - duration: duration in 100-nanosecond units

    Only words (not silence markers) are included in the output.
    """
    cfg = get_settings()
    rate = _speed_to_streak(cfg.voice_speed)
    volume = f"+{int((cfg.voice_volume - 1.0) * 100)}%"

    communicate = edge_tts.Communicate(
        text=text,
        voice=cfg.voice_name,
        rate=rate,
        volume=volume,
    )

    timestamps: list[dict[str, str | float]] = []

    with open(output_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word = chunk.get("text", "").strip()
                if not word:
                    continue
                offset_us = chunk.get("offset", 0)
                duration_us = chunk.get("duration", 0)
                start_sec = offset_us / 10_000_000
                end_sec = (offset_us + duration_us) / 10_000_000
                timestamps.append({
                    "word": word,
                    "start": round(start_sec, 3),
                    "end": round(end_sec, 3),
                })

    output_data = {
        "full_text": text,
        "timestamps": timestamps,
    }
    with open(timestamps_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    logger.info(
        "Generated %d word timestamps for %.1fs of audio",
        len(timestamps),
        timestamps[-1]["end"] if timestamps else 0,
    )
    return timestamps


def generate_voiceover(
    hook: str,
    points: list[str],
    cta: str,
    output_path: str,
) -> list[dict]:
    """Generate a voiceover audio file and word-level timestamps.

    Args:
        hook: Attention-grabbing opening sentence.
        points: List of bullet-point content sentences.
        cta: Call-to-action closing sentence.
        output_path: Path to write the output audio file (e.g. .mp3).

    Returns:
        List of timestamp dicts with keys: word, start, end.

    Raises:
        VoiceError: If generation fails or output file is invalid.
    """
    text = build_text(hook, points, cta)
    ts_path = str(Path(output_path).with_suffix(".timestamps.json"))

    logger.debug("Generating voiceover for text (%d chars)", len(text))

    try:
        timestamps = _run_async(
            _generate_with_timestamps(text, output_path, ts_path)
        )
    except Exception as exc:
        raise VoiceError(f"Voiceover generation failed: {exc}") from exc

    _verify_audio_file(output_path)
    logger.info("Voiceover saved to: %s", output_path)
    return timestamps
