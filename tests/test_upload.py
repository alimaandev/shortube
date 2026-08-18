"""Thumbnail generation (Pillow) respects base_dir-relative assets."""

from __future__ import annotations

from PIL import Image

from shortube.upload import generate_thumbnail


def test_thumbnail_uses_base_dir_assets(settings, tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    Image.new("RGB", (64, 64), (200, 30, 30)).save(assets / "thumbnail_bg.png")

    out = tmp_path / "thumb.jpg"
    generate_thumbnail(
        "A Great Title About Cats", str(out), subtitle="Did you know?"
    )
    assert out.exists()
    assert out.stat().st_size > 5000
    assert Image.open(out).size == (1280, 720)


def test_thumbnail_without_background_asset(settings, tmp_path):
    out = tmp_path / "thumb2.jpg"
    generate_thumbnail("Plain Title", str(out))
    assert out.exists()
