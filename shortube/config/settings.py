from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Paths ──────────────────────────────────────────────────────────
    base_dir: Path = Path(__file__).resolve().parent.parent.parent
    assets_dir: Path | None = None
    cache_dir: Path | None = None

    # ── API Keys ───────────────────────────────────────────────────────
    groq_api_key: str = ""
    pexels_api_key: str = ""

    # ── YouTube OAuth ──────────────────────────────────────────────────
    youtube_client_secrets: str = "client_secrets.json"
    youtube_scopes: list[str] = ["https://www.googleapis.com/auth/youtube.upload"]

    # ── Content defaults ───────────────────────────────────────────────
    niche: str = "general_facts"
    script_language: str = "en"

    # ── Voice (Edge-TTS) ───────────────────────────────────────────────
    voice_name: str = "en-US-AriaNeural"
    voice_speed: float = 1.15
    voice_volume: float = 1.0
    voice_style: str = "default"  # "ssml" to use SSML breaks and emphasis

    # ── Video assembly ─────────────────────────────────────────────────
    video_width: int = 1080
    video_height: int = 1920
    video_fps: int = 30
    clip_min_duration: float = 3.0
    transition_duration: float = 0.3
    clips_per_keyword: int = 2
    bumper_duration: float = 1.5
    ken_burns: bool = True

    # ── Audio ─────────────────────────────────────────────────────────
    background_music_path: str = ""
    music_volume: float = 15.0
    duck_threshold: float = 6.0

    # ── Captions ───────────────────────────────────────────────────────
    caption_font: str = "C:/Windows/Fonts/arial.ttf"
    caption_font_size: int = 48
    caption_font_color: str = "white"
    caption_stroke_color: str = "black"
    caption_stroke_width: int = 3

    # ── Upload defaults ────────────────────────────────────────────────
    upload_privacy: str = "private"
    upload_category: str = "22"
    upload_language: str = "en"
    tags_default: list[str] = ["shorts", "youtubeshorts"]
    upload_publish_at: str = ""
    upload_playlist_id: str = ""

    # ── LLM (Groq) ─────────────────────────────────────────────────────
    llm_provider: Literal["groq"] = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    discovery_model: str = "llama-3.3-70b-versatile"
    llm_temperature: float = 0.8
    llm_max_tokens: int = 800

    # ── Discovery ──────────────────────────────────────────────────────
    discovery_niche: str = "general_facts"

    # ── Quality ────────────────────────────────────────────────────────
    quality_pass_threshold: int = 7
    quality_max_retries: int = 3

    # ── Cache ──────────────────────────────────────────────────────────
    cache_default_ttl: int = 3600

    def _resolve(self) -> None:
        if self.assets_dir is None:
            self.assets_dir = self.base_dir / "shortube" / "assets"
        if self.cache_dir is None:
            self.cache_dir = self.base_dir / "shortube" / "cache"
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def model_post_init(self, _context) -> None:
        self._resolve()


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
