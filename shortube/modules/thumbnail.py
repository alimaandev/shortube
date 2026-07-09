from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from shortube.config.settings import get_settings

logger = logging.getLogger(__name__)


def generate_thumbnail(
    title: str,
    output_path: str,
    subtitle: str = "",
    font_path: str | None = None,
) -> str:
    width, height = 1280, 720
    img = Image.new("RGB", (width, height), (10, 10, 10))

    draw = ImageDraw.Draw(img)

    bg_path = Path("assets/thumbnail_bg.png")
    if bg_path.exists():
        try:
            bg = Image.open(bg_path).resize((width, height))
            img.paste(bg, (0, 0))
        except Exception as e:
            logger.warning("Failed to load thumbnail background: %s", e)

    try:
        title_font = ImageFont.truetype(font_path or "C:/Windows/Fonts/arialbd.ttf", 56)
        subtitle_font = ImageFont.truetype(font_path or "C:/Windows/Fonts/arial.ttf", 32)
    except Exception:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()

    lines = []
    words = title.split()
    line = ""
    for word in words:
        test = f"{line} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=title_font)
        if bbox[2] - bbox[0] > width - 80:
            lines.append(line)
            line = word
        else:
            line = test
    if line:
        lines.append(line)

    y = height // 2 - (len(lines) * 30)
    for i, line_text in enumerate(lines):
        bbox = draw.textbbox((0, 0), line_text, font=title_font)
        tw = bbox[2] - bbox[0]
        x = (width - tw) // 2
        draw.text((x + 2, y + 2), line_text, fill="black", font=title_font)
        draw.text((x, y), line_text, fill="white", font=title_font)
        y += 65

    if subtitle:
        bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
        sw = bbox[2] - bbox[0]
        sx = (width - sw) // 2
        sy = y + 10
        draw.text((sx + 1, sy + 1), subtitle, fill="black", font=subtitle_font)
        draw.text((sx, sy), subtitle, fill="#cccccc", font=subtitle_font)

    img.save(output_path, "JPEG", quality=95)
    logger.info("Thumbnail saved to %s", output_path)
    return output_path