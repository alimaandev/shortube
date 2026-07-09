from __future__ import annotations

import logging
from typing import Any

import requests

from shortube.core.types import MediaAsset
from shortube.shared.retry import retry

PIXABAY_VIDEO_URL = "https://pixabay.com/api/videos/"
PIXABAY_IMAGE_URL = "https://pixabay.com/api/"

logger = logging.getLogger(__name__)


class PixabayProvider:
    name = "pixabay"

    def __init__(self, api_key: str = ""):
        self._api_key = api_key

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
        params: dict[str, Any] = {
            "q": query,
            "per_page": min(max_results, 50),
            "safesearch": "true",
        }
        if orientation == "portrait":
            params["orientation"] = "vertical"
        if self._api_key:
            params["key"] = self._api_key

        resp = requests.get(PIXABAY_VIDEO_URL, params=params, timeout=15,
                            headers={"User-Agent": "ShortsAutomator/1.0"})
        if resp.status_code != 200:
            logger.warning("Pixabay video search returned %d", resp.status_code)
            return []

        data = resp.json()
        assets: list[MediaAsset] = []
        for hit in data.get("hits", []):
            videos = hit.get("videos", {})
            # Prefer large, then medium, then small
            for size in ("large", "medium", "small"):
                video_info = videos.get(size)
                if video_info:
                    assets.append(
                        MediaAsset(
                            url=video_info["url"],
                            type="video",
                            provider="pixabay",
                            width=video_info.get("width", 1080),
                            height=video_info.get("height", 1920),
                            duration=hit.get("duration", 0),
                        )
                    )
                    break
        return assets

    @retry(max_attempts=2, exceptions=(requests.RequestException,))
    def _search_photos(self, query: str, orientation: str, max_results: int) -> list[MediaAsset]:
        params: dict[str, Any] = {
            "q": query,
            "per_page": min(max_results, 50),
            "safesearch": "true",
        }
        if orientation == "portrait":
            params["orientation"] = "vertical"
        if self._api_key:
            params["key"] = self._api_key

        resp = requests.get(PIXABAY_IMAGE_URL, params=params, timeout=15,
                            headers={"User-Agent": "ShortsAutomator/1.0"})
        if resp.status_code != 200:
            logger.warning("Pixabay photo search returned %d", resp.status_code)
            return []
        data = resp.json()
        return [
            MediaAsset(
                url=hit["webformatURL"],
                type="image",
                provider="pixabay",
                width=hit.get("imageWidth", 1080),
                height=hit.get("imageHeight", 1920),
            )
            for hit in data.get("hits", [])
        ]
