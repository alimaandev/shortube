from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_dir: Path = Path(__file__).resolve().parent.parent

    groq_api_key: str = ""
    openrouter_api_key: str = ""
    pexels_api_key: str = ""
    pixabay_api_key: str = ""

    youtube_client_secrets: str = "client_secrets.json"
    youtube_scopes: list[str] = [
        "https://www.googleapis.com/auth/youtube.upload"
    ]

    niche: str = "general_facts"

    voice_name: str = "en-US-AriaNeural"
    voice_speed: float = 1.15
    voice_volume: float = 1.0

    video_width: int = 1080
    video_height: int = 1920
    video_fps: int = 30
    transition_duration: float = 0.3
    bumper_duration: float = 1.5

    background_music_path: str = ""
    music_volume: float = 15.0
    duck_threshold: float = 6.0

    caption_font: str = "C:/Windows/Fonts/arial.ttf"
    caption_font_size: int = 48
    caption_font_color: str = "white"
    caption_stroke_color: str = "black"
    caption_stroke_width: int = 3

    upload_privacy: str = "public"
    upload_category: str = "22"
    upload_language: str = "en"
    tags_default: list[str] = ["shorts", "youtubeshorts"]
    upload_channel_id: str = ""
    upload_publish_at: str = ""
    upload_playlist_id: str = ""

    llm_provider: Literal["groq", "openrouter", "ollama"] = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    discovery_model: str = "llama-3.3-70b-versatile"
    llm_temperature: float = 0.8
    llm_max_tokens: int = 800
    ollama_base_url: str = "http://localhost:11434"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
