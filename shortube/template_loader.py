"""Config-driven visual templates (templates/*.json).

Templates define the full visual identity of a render: colors, fonts,
transition style, Ken Burns behavior, caption styling, hook flash and
outro styling. Settings override the template name; missing or invalid
templates fall back to the bundled defaults so a render can never fail
on a template problem.
"""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

from shortube.config import get_settings

logger = logging.getLogger(__name__)

DEFAULTS: dict[str, Any] = {
    "id": "premium",
    "name": "Premium Bold",
    "accent": "#4caf50",
    "accent2": "#81c784",
    "background": "#0a0a0a",
    "background2": "#141414",
    "text": "#ffffff",
    "muted": "#aaaaaa",
    "gradient": "135deg, #0a0a0a 0%, #1a1a1a 50%, #0d2b0d 100%",
    "font": "'Segoe UI', -apple-system, Roboto, Helvetica, Arial, sans-serif",
    "transition": "zoomBlur",
    "kenBurns": True,
    "kenBurnsIntensity": 1.1,
    "captionStyle": {
        "backgroundColor": "rgba(0, 0, 0, 0.55)",
        "strokeColor": "rgba(0, 0, 0, 0.85)",
        "highlightColor": "#ffffff",
        "accentColor": "#4caf50",
        "fontSize": 34,
    },
    "hook": {
        "flashColor": "rgba(255, 255, 255, 0.5)",
        "keywordColor": "#ffd54f",
    },
    "outro": {
        "subscribeColor": "#4caf50",
        "tagline": "Follow for more",
    },
}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load_template(name: str = "") -> dict[str, Any]:
    """Load a visual template by name. Falls back to premium, then defaults."""
    cfg = get_settings()
    templates_dir = Path(cfg.base_dir) / "templates"
    resolved = name or "premium"

    candidates = []
    if resolved:
        candidates.append(templates_dir / f"{resolved}.json")
    if resolved != "premium":
        candidates.append(templates_dir / "premium.json")

    for candidate in candidates:
        try:
            if candidate.exists():
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    logger.warning("Template %s is not an object", candidate)
                    continue
                return _merge(DEFAULTS, data)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load template %s: %s", candidate, exc)

    logger.warning("Template '%s' not found — using built-in defaults", resolved)
    return copy.deepcopy(DEFAULTS)
