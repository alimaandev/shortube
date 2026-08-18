"""Persist application settings to the .env file.

Used by the desktop Settings page and the first-run setup wizard so that
changes apply immediately (a cached settings reload follows each save).

The field name <-> env variable mapping lives in `shortube.config`
(the Settings model's alias generator); this module is a thin I/O layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shortube.config import env_key, get_settings, reset_settings


def env_path() -> Path:
    return get_settings().base_dir / ".env"


def save_settings(payload: dict[str, Any]) -> None:
    """Upsert the given fields into .env and reload the settings cache.

    Only the keys present in the payload are touched; anything else in
    the file (API keys, provider settings, ...) is left alone. A value
    of `None` removes the key entirely.
    """
    env_file = env_path()
    lines: list[str] = []
    if env_file.exists():
        lines = env_file.read_text(encoding="utf-8").splitlines()

    targets: dict[str, Any] = {}
    for py_key, value in payload.items():
        env_key_name = env_key(py_key)
        if isinstance(value, bool):
            value = str(value).lower()
        elif isinstance(value, list):
            value = ",".join(str(v) for v in value)
        targets[env_key_name] = value

    kept: list[str] = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            kept.append(line)
            continue
        key, _, _ = line.partition("=")
        if key.strip() in targets:
            continue  # replaced or removed below
        kept.append(line)

    for key, value in targets.items():
        if value is None:
            continue  # key already dropped from the file
        kept.append(f"{key}={value}")

    env_file.write_text("\n".join(kept) + "\n", encoding="utf-8")
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
