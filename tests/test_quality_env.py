"""Quality presets and .env settings round-trip."""

from __future__ import annotations

from shortube.quality import DEFAULT_QUALITY, QUALITY_PRESETS, resolve_preset
from shortube.settings_env import read_env, save_settings


def test_fast_preset_values():
    p = resolve_preset("fast")
    assert p.fps == 24
    assert p.concurrency == 2
    assert p.crf == 22
    assert p.audio_bitrate == "160k"


def test_pro_preset_values():
    p = resolve_preset("pro")
    assert p.fps == 30
    assert p.crf == 14
    assert p.audio_bitrate == "256k"
    assert p.concurrency >= 2


def test_unknown_preset_falls_back():
    assert (
        resolve_preset("bogus").label
        == QUALITY_PRESETS[DEFAULT_QUALITY].label
    )


def test_empty_preset_falls_back():
    assert (
        resolve_preset("").label
        == QUALITY_PRESETS[DEFAULT_QUALITY].label
    )


def test_settings_round_trip(settings, tmp_path):
    save_settings({
        "llm_provider": "ollama",
        "llm_temperature": 0.8,
        "sfx_enabled": False,
        "tags_default": ["a", "b"],
    })
    env = read_env()
    assert env["LLM_PROVIDER"] == "ollama"
    assert env["LLM_TEMPERATURE"] == "0.8"
    assert env["SFX_ENABLED"] == "false"
    assert env["TAGS_DEFAULT"] == "a,b"


def test_settings_replacement(settings, tmp_path):
    save_settings({"llm_provider": "ollama"})
    save_settings({"llm_provider": "groq"})
    env = read_env()
    assert env["LLM_PROVIDER"] == "groq"


def test_settings_written_to_base_dir(settings, tmp_path):
    save_settings({"niche": "space"})
    assert (tmp_path / ".env").exists()
    assert read_env()["NICHE"] == "space"


def test_saving_without_key_preserves_existing_keys(settings, tmp_path):
    save_settings({"groq_api_key": "sk-secret-123"})
    save_settings({"niche": "space"})
    env = read_env()
    assert env["GROQ_API_KEY"] == "sk-secret-123"
    assert env["NICHE"] == "space"


def test_none_value_removes_key(settings, tmp_path):
    save_settings({"groq_api_key": "sk-secret-123"})
    save_settings({"groq_api_key": None})
    assert "GROQ_API_KEY" not in read_env()


def test_env_alias_matches_settings_loading(settings, tmp_path):
    # The alias generator must agree with what Settings() reads from .env,
    # otherwise the GUI writes keys the model never sees.
    save_settings({
        "caption_font_size": 52,
        "upload_publish_at": "2026-09-01T10:00:00Z",
        "sfx_enabled": False,
    })
    from shortube.config import Settings

    fresh = Settings(_env_file=str(tmp_path / ".env"))
    assert fresh.caption_font_size == 52
    assert fresh.upload_publish_at == "2026-09-01T10:00:00Z"
    assert fresh.sfx_enabled is False
