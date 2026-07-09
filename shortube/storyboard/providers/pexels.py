from __future__ import annotations

import logging
from pathlib import Path

import requests

from shortube.core.types import MediaAsset
from shortube.shared.retry import retry

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"
PEXELS_PHOTO_URL = "https://api.pexels.com/v1/search"

logger = logging.getLogger(__name__)


class PexelsProvider:
    name = "pexels"

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._headers = {"Authorization": api_key}

    def search(
        self,
        query: str,
        media_type: str = "video",
        orientation: str = "portrait",
        max_results: int = 10,
    ) -> list[MediaAsset]:
        if media_type == "video":
            return self._search_videos(query, orientation, max_results)
        return self._search_photos(query, orientation, max_results)

    @retry(max_attempts=2, exceptions=(requests.RequestException,))
    def _search_videos(self, query: str, orientation: str, max_results: int) -> list[MediaAsset]:
        resp = requests.get(
            PEXELS_SEARCH_URL,
            headers=self._headers,
            params={"query": query, "per_page": max_results, "orientation": orientation},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning("Pexels video search returned %d", resp.status_code)
            return []

        data = resp.json()
        assets: list[MediaAsset] = []
        for video in data.get("videos", []):
            clip_url = self._best_quality(video.get("video_files", []))
            if not clip_url:
                continue
            duration = video.get("duration", 0)
            if duration < 3.0:
                continue
            assets.append(
                MediaAsset(
                    url=clip_url,
                    type="video",
                    provider="pexels",
                    width=video.get("width", 1080),
                    height=video.get("height", 1920),
                    duration=duration,
                )
            )
        return assets

    @retry(max_attempts=2, exceptions=(requests.RequestException,))
    def _search_photos(self, query: str, orientation: str, max_results: int) -> list[MediaAsset]:
        resp = requests.get(
            PEXELS_PHOTO_URL,
            headers=self._headers,
            params={"query": query, "per_page": max_results, "orientation": orientation},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning("Pexels photo search returned %d", resp.status_code)
            return []
        data = resp.json()
        return [
            MediaAsset(
                url=photo["src"]["original"],
                type="image",
                provider="pexels",
                width=photo.get("width", 1080),
                height=photo.get("height", 1920),
            )
            for photo in data.get("photos", [])
        ]

    @staticmethod
    def _best_quality(files: list[dict]) -> str | None:
        candidates = [f for f in files if f.get("quality") in ("hd", "sd")]
        if not candidates:
            return None
        best = max(candidates, key=lambda f: f.get("width", 0) * f.get("height", 0))
        return best.get("link")

    @staticmethod
    def download(url: str, dest: Path) -> str:
        r = requests.get(url, stream=True, timeout=30)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return str(dest)
