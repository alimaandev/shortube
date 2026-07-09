import asyncio
import json
import re
from pathlib import Path

import edge_tts

from shortube.config import VOICE_NAME, VOICE_SPEED, VOICE_VOLUME


def _speed_to_streak(speed: float) -> str:
    return f"+{int((speed - 1.0) * 100)}%"


def _ssml_emphasize(text: str) -> str:
    text = re.sub(r"(\b\d+[%]?\b)", r'<emphasis level="moderate">\1</emphasis>', text)
    text = re.sub(
        r"\b(extremely|incredibly|absolutely|literally|massive|huge|shocking|unbelievable|mind\.blowing|crazy|insane)\b",
        r'<emphasis level="strong">\1</emphasis>',
        text,
        flags=re.IGNORECASE,
    )
    return text


def build_ssml(hook: str, points: list[str], cta: str) -> str:
    parts = [f"<p>{_ssml_emphasize(hook)}</p>"]
    for pt in points:
        parts.append(f'<break time="300ms"/><p>{_ssml_emphasize(pt)}</p>')
    parts.append(f'<break time="400ms"/><p>{_ssml_emphasize(cta)}</p>')
    return f"<speak version='1.1' xmlns='http://www.w3.org/2001/10/synthesis'>{''.join(parts)}</speak>"


async def _generate(text: str, output_path: str) -> None:
    tts = edge_tts.Communicate(
        text=text,
        voice=VOICE_NAME,
        rate=_speed_to_streak(VOICE_SPEED),
        volume=f"+{int((VOICE_VOLUME - 1.0) * 100)}%",
    )
    await tts.save(output_path)


async def _generate_with_timestamps(
    text: str, output_path: str, timestamps_path: str,
) -> dict:
    """Generate voiceover and capture word-level timestamps from stream."""
    tts = edge_tts.Communicate(
        text=text,
        voice=VOICE_NAME,
        rate=_speed_to_streak(VOICE_SPEED),
        volume=f"+{int((VOICE_VOLUME - 1.0) * 100)}%",
    )
    timestamps: list[dict] = []
    with open(output_path, "wb") as f:
        async for chunk in tts.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                offset_ms = chunk.get("offset", 0) / 1e4
                duration_ms = chunk.get("duration", 0) / 1e4
                timestamps.append({
                    "word": chunk.get("text", ""),
                    "start": round(offset_ms / 1000, 3),
                    "end": round((offset_ms + duration_ms) / 1000, 3),
                })

    output = {"timestamps": timestamps, "full_text": text}
    with open(timestamps_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    return output


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return loop.create_task(coro)
        else:
            return loop.run_until_complete(coro)


def generate_voiceover(text: str, output_path: str) -> str:
    _run_async(_generate(text, output_path))
    return output_path


def generate_voiceover_ssml(
    hook: str, points: list[str], cta: str, output_path: str
) -> str:
    ssml = build_ssml(hook, points, cta)
    return generate_voiceover(ssml, output_path)


def generate_voiceover_with_timestamps(
    hook: str,
    points: list[str],
    cta: str,
    output_path: str,
) -> list[dict]:
    """Generate SSML voiceover and return sentence-level timestamps.

    Returns list of {"word": str, "start": float, "end": float}.
    When edge-tts provides per-word boundaries, those are captured.
    Otherwise sentence boundaries are returned.
    """
    ssml = build_ssml(hook, points, cta)
    ts_path = str(Path(output_path).with_suffix(".timestamps.json"))
    result = _run_async(_generate_with_timestamps(ssml, output_path, ts_path))
    return result["timestamps"]
