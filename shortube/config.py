"""Application settings.

Single source of truth: the `Settings` pydantic model below maps every
field to its .env variable via the `_to_env_alias` generator, so the
GUI key <-> env key mapping (KEY_MAP in earlier builds) can never drift.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


def _to_env_alias(name: str) -> str:
    """`caption_font_size` -> `CAPTION_FONT_SIZE` (used for .env keys)."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        alias_generator=_to_env_alias,
        populate_by_name=True,
    )

    base_dir: Path = Path(__file__).resolve().parent.parent

    groq_api_key: str = ""
    openrouter_api_key: str = ""
    pexels_api_key: str = ""
    pixabay_api_key: str = ""

    youtube_client_secrets: str = "client_secrets.json"
    youtube_scopes: list[str] = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
    ]

    niche: str = "general_facts"

    voice_name: str = "en-US-AriaNeural"
    voice_speed: float = 1.15
    voice_volume: float = 1.0

    video_width: int = 1080
    video_height: int = 1920
    video_fps: int = 30
    bumper_duration: float = 1.5
    transition_duration: float = 0.3
    template: str = ""

    background_music_path: str = ""
    music_volume: float = 15.0
    duck_threshold: float = 6.0
    sfx_enabled: bool = True
    sfx_dir: str = "resources/sfx"

    caption_font_size: int = 48

    upload_privacy: str = "public"
    upload_category: str = "22"
    upload_language: str = "en"
    tags_default: list[str] = ["shorts", "youtubeshorts"]
    upload_channel_id: str = ""
    upload_publish_at: str = ""
    upload_playlist_id: str = ""

    llm_provider: Literal["groq", "openrouter", "ollama"] = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    discovery_model: str = ""
    llm_temperature: float = 0.8
    llm_max_tokens: int = 800
    ollama_base_url: str = "http://localhost:11434"

    image_provider: str = "auto"
    media_prefer_videos: bool = True

    quality: str = "standard"

    remotion_project_dir: str = "remotion"
    remotion_concurrency: int = 0


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Drop the cached settings so the next get_settings() re-reads .env."""
    global _settings
    _settings = None


def env_key(field_name: str) -> str:
    """The .env variable name for a Settings field (e.g. 'video_fps')."""
    return _to_env_alias(field_name)


def all_env_keys() -> set[str]:
    """Every .env variable name the Settings model understands."""
    return {_to_env_alias(name) for name in Settings.model_fields}
