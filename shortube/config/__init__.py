"""
Backward-compatible re-exports + new Settings API.

Old code: from shortube.config import GROQ_API_KEY     # still works
New code: from shortube.config.settings import Settings # preferred
"""
from shortube.config.settings import Settings, get_settings

settings = get_settings()

# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = settings.base_dir
ASSETS_DIR = settings.assets_dir
OUTPUT_DIR = settings.assets_dir / "output"
DRAFT_DIR = settings.assets_dir / "drafts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DRAFT_DIR.mkdir(parents=True, exist_ok=True)

# ── API Keys ───────────────────────────────────────────────────────────
GROQ_API_KEY = settings.groq_api_key
PEXELS_API_KEY = settings.pexels_api_key

# ── YouTube OAuth ──────────────────────────────────────────────────────
YOUTUBE_CLIENT_SECRETS = settings.youtube_client_secrets
YOUTUBE_SCOPES = settings.youtube_scopes

# ── Content ────────────────────────────────────────────────────────────
NICHE = settings.niche
SCRIPT_LANGUAGE = settings.script_language

# ── Voice ──────────────────────────────────────────────────────────────
VOICE_NAME = settings.voice_name
VOICE_SPEED = settings.voice_speed
VOICE_VOLUME = settings.voice_volume

# ── Video assembly ─────────────────────────────────────────────────────
VIDEO_WIDTH = settings.video_width
VIDEO_HEIGHT = settings.video_height
VIDEO_FPS = settings.video_fps
CLIP_MIN_DURATION = settings.clip_min_duration
TRANSITION_DURATION = settings.transition_duration
CLIPS_PER_KEYWORD = settings.clips_per_keyword
BUMPER_DURATION = settings.bumper_duration

# ── Captions ───────────────────────────────────────────────────────────
CAPTION_FONT = settings.caption_font
CAPTION_FONT_SIZE = settings.caption_font_size
CAPTION_FONT_COLOR = settings.caption_font_color
CAPTION_STROKE_COLOR = settings.caption_stroke_color
CAPTION_STROKE_WIDTH = settings.caption_stroke_width

# ── Upload ─────────────────────────────────────────────────────────────
UPLOAD_PRIVACY = settings.upload_privacy
UPLOAD_CATEGORY = settings.upload_category
UPLOAD_LANGUAGE = settings.upload_language
TAGS_DEFAULT = settings.tags_default

# ── LLM / Discovery ────────────────────────────────────────────────────
DISCOVERY_MODEL = settings.discovery_model
DISCOVERY_NICHE = settings.discovery_niche

__all__ = [
    "Settings", "get_settings", "settings",
    "BASE_DIR", "ASSETS_DIR", "OUTPUT_DIR", "DRAFT_DIR",
    "GROQ_API_KEY", "PEXELS_API_KEY",
    "YOUTUBE_CLIENT_SECRETS", "YOUTUBE_SCOPES",
    "NICHE", "SCRIPT_LANGUAGE",
    "VOICE_NAME", "VOICE_SPEED", "VOICE_VOLUME",
    "VIDEO_WIDTH", "VIDEO_HEIGHT", "VIDEO_FPS",
    "CLIP_MIN_DURATION", "TRANSITION_DURATION", "CLIPS_PER_KEYWORD", "BUMPER_DURATION",
    "CAPTION_FONT", "CAPTION_FONT_SIZE", "CAPTION_FONT_COLOR",
    "CAPTION_STROKE_COLOR", "CAPTION_STROKE_WIDTH",
    "UPLOAD_PRIVACY", "UPLOAD_CATEGORY", "UPLOAD_LANGUAGE", "TAGS_DEFAULT",
    "DISCOVERY_MODEL", "DISCOVERY_NICHE",
]
