"""Persist application settings to the .env file.

Used by the desktop Settings page and the first-run setup wizard so that
changes apply immediately (a cached settings reload follows each save).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shortube.config import get_settings, reset_settings

# Maps GUI field name -> .env variable name.
KEY_MAP: dict[str, str] = {
    "niche": "NICHE",
    "voice_name": "VOICE_NAME",
    "voice_speed": "VOICE_SPEED",
    "voice_volume": "VOICE_VOLUME",
    "video_width": "VIDEO_WIDTH",
    "video_height": "VIDEO_HEIGHT",
    "video_fps": "VIDEO_FPS",
    "bumper_duration": "BUMPER_DURATION",
    "transition_duration": "TRANSITION_DURATION",
    "template": "TEMPLATE",
    "background_music_path": "BACKGROUND_MUSIC_PATH",
    "music_volume": "MUSIC_VOLUME",
    "duck_threshold": "DUCK_THRESHOLD",
    "sfx_enabled": "SFX_ENABLED",
    "sfx_dir": "SFX_DIR",
    "caption_font_size": "CAPTION_FONT_SIZE",
    "upload_privacy": "UPLOAD_PRIVACY",
    "upload_category": "UPLOAD_CATEGORY",
    "upload_language": "UPLOAD_LANGUAGE",
    "upload_channel_id": "UPLOAD_CHANNEL_ID",
    "upload_publish_at": "UPLOAD_PUBLISH_AT",
    "upload_playlist_id": "UPLOAD_PLAYLIST_ID",
    "llm_provider": "LLM_PROVIDER",
    "llm_model": "LLM_MODEL",
    "discovery_model": "DISCOVERY_MODEL",
    "llm_temperature": "LLM_TEMPERATURE",
    "llm_max_tokens": "LLM_MAX_TOKENS",
    "ollama_base_url": "OLLAMA_BASE_URL",
    "groq_api_key": "GROQ_API_KEY",
    "openrouter_api_key": "OPENROUTER_API_KEY",
    "tags_default": "TAGS_DEFAULT",
    "image_provider": "IMAGE_PROVIDER",
    "image_provider_fallback": "IMAGE_PROVIDER_FALLBACK",
    "media_prefer_videos": "MEDIA_PREFER_VIDEOS",
    "quality": "QUALITY",
    "remotion_concurrency": "REMOTION_CONCURRENCY",
}


def env_path() -> Path:
    return get_settings().base_dir / ".env"


def save_settings(payload: dict[str, Any]) -> None:
    """Merge the given fields into .env (replacing existing keys) and reload."""
    env_file = env_path()
    lines: list[str] = []
    if env_file.exists():
        lines = env_file.read_text(encoding="utf-8").splitlines()

    keys_to_remove = set(KEY_MAP.values())
    lines = [
        line for line in lines
        if not any(line.startswith(k + "=") for k in keys_to_remove)
    ]

    new_lines: list[str] = []
    for py_key, env_key in KEY_MAP.items():
        if py_key in payload:
            val = payload[py_key]
            if isinstance(val, bool):
                val = str(val).lower()
            elif isinstance(val, list):
                val = ",".join(str(v) for v in val)
            new_lines.append(f"{env_key}={val}")

    lines.extend(new_lines)
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    reset_settings()


def read_env() -> dict[str, str]:
    """Return the raw key=value pairs currently in .env."""
    env_file = env_path()
    out: dict[str, str] = {}
    if not env_file.exists():
        return out
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out
