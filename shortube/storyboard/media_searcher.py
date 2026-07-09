from __future__ import annotations

import logging
from typing import Sequence

from shortube.config import PEXELS_API_KEY
from shortube.core.types import MediaAsset
from shortube.storyboard.providers import ImageFallbackProvider, PexelsProvider, PixabayProvider

logger = logging.getLogger(__name__)


class MediaSearcher:
    def __init__(self):
        self._providers: list = []
        if PEXELS_API_KEY:
            self._providers.append(PexelsProvider(PEXELS_API_KEY))
        self._providers.append(PixabayProvider())
        self._providers.append(ImageFallbackProvider())

    def add_provider(self, provider) -> MediaSearcher:
        self._providers.append(provider)
        return self

    def search(
        self,
        queries: Sequence[str],
        max_per_query: int = 2,
        orientation: str = "portrait",
    ) -> list[MediaAsset]:
        results: list[MediaAsset] = []
        seen_urls: set[str] = set()

        for query in queries:
            for provider in self._providers:
                try:
                    assets = provider.search(
                        query,
                        media_type="video",
                        orientation=orientation,
                        max_results=max_per_query * 2,
                    )
                    for asset in assets:
                        if asset.url not in seen_urls:
                            seen_urls.add(asset.url)
                            results.append(asset)
                except Exception as e:
                    logger.warning("Provider %s failed for '%s': %s", provider.name, query, e)

            if len(results) >= max_per_query * len(queries):
                break

        return results[: max_per_query * len(queries)]
