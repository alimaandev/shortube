"""Storyboard media download manager: size caps, caching, downscaling."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

import shortube.storyboard as sb


def _make_jpeg(size, color=(10, 200, 10)):
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


class FakeResp:
    def __init__(self, body, content_type="image/jpeg"):
        self._body = body
        self.status_code = 200
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(body)),
        }

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=32768):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i : i + chunk_size]


class FakeRespNoLen(FakeResp):
    def __init__(self, body):
        super().__init__(body)
        self.headers = {"Content-Type": "image/jpeg"}


def _session_with(resp):
    return type("S", (), {"get": lambda self, *a, **kw: resp})()


def test_content_length_cap_rejects(tmp_path):
    dm = sb.DownloadManager(tmp_path / "cache")
    dm._session = _session_with(FakeResp(b"x" * (sb.MAX_IMAGE_BYTES + 1)))
    assert dm.get("http://x/len.jpg", "image") is None


def test_streaming_cap_aborts_mid_download(tmp_path):
    dm = sb.DownloadManager(tmp_path / "cache")
    dm._session = _session_with(FakeRespNoLen(b"x" * (sb.MAX_IMAGE_BYTES + 1)))
    assert dm.get("http://x/stream.jpg", "image") is None


def test_small_image_downloaded_and_cached(tmp_path):
    dm = sb.DownloadManager(tmp_path / "cache")
    dm._session = _session_with(FakeResp(_make_jpeg((640, 640))))
    p = dm.get("http://x/small.jpg", "image")
    assert p and Path(p).exists()


def test_oversized_image_is_downscaled(tmp_path):
    dm = sb.DownloadManager(tmp_path / "cache")
    dm._session = _session_with(FakeResp(_make_jpeg((5000, 3000), (30, 30, 200))))
    p2 = dm.get("http://x/big.jpg", "image")
    assert p2 and Path(p2).exists()
    with Image.open(p2) as im:
        w, h = im.size
    assert w <= sb.MAX_IMAGE_DIMENSION and h <= sb.MAX_IMAGE_DIMENSION
    assert w == 2560
    assert dm._cache_index["http://x/big.jpg"] == p2


def test_video_size_cap_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(sb, "MAX_VIDEO_BYTES", 4000)
    vp = tmp_path / "vid.mp4"
    vp.write_bytes(b"x" * 5000)
    assert sb.DownloadManager(tmp_path / "cache")._validate_file(vp, "video") is False
