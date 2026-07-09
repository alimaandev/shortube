from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from shortube.config.settings import get_settings
from shortube.core.interfaces import StoryboardGenerator
from shortube.core.types import MediaAsset, Scene, Script, Storyboard
from shortube.shared.cache import DiskCache
from shortube.shared.llm import LLMProvider
from shortube.shared.logging import get_logger
from shortube.storyboard.media_searcher import MediaSearcher
from shortube.storyboard.query_generator import QueryGenerator
from shortube.storyboard.query_ranker import rank_queries
from shortube.storyboard.scene_splitter import SceneSplitter


class StoryboardEngine(StoryboardGenerator):
    def __init__(
        self,
        llm: LLMProvider,
        cache: DiskCache | None = None,
    ):
        self._llm = llm
        self._logger = get_logger("storyboard")
        self._cache = cache

        self._assets_dir = get_settings().assets_dir
        self._scene_splitter = SceneSplitter(llm)
        self._query_generator = QueryGenerator(llm)
        self._media_searcher = MediaSearcher()

    def set_media_searcher(self, searcher: MediaSearcher) -> StoryboardEngine:
        self._media_searcher = searcher
        return self

    def generate(self, script: Script, voiceover_path: str) -> Storyboard:
        from moviepy import AudioFileClip

        self._logger.info("Generating storyboard for: %s", script.topic[:50])

        # Get audio duration
        audio = AudioFileClip(voiceover_path)
        total_duration = audio.duration

        # Split script into scenes
        scenes = self._scene_splitter.split(script, total_duration)

        # Generate and rank search queries per scene
        for scene in scenes:
            scene.search_queries = self._query_generator.generate(scene)
            rank_queries(scene)

        # Search media per scene
        for scene in scenes:
            if not scene.search_queries:
                continue

            # Cache key based on scene content hash
            cache_key = f"media:{scene.index}:{hashlib.sha256(scene.visual_description.encode()).hexdigest()[:16]}"
            cached: list[dict] | None = None
            if self._cache:
                cached = self._cache.get(cache_key)

            if cached is not None:
                scene.selected_media = [
                    MediaAsset(**item) for item in cached
                ]
            else:
                from shortube.storyboard.semantic_ranker import rank_assets_by_relevance
                assets = self._media_searcher.search(scene.search_queries)
                assets = rank_assets_by_relevance(assets, scene.visual_description)
                for asset in assets:
                    if asset.provider == "fallback":
                        continue
                    asset.local_path = self._download_asset(asset, scene)
                scene.selected_media = assets[:3]
                if self._cache and assets:
                    self._cache.set(
                        cache_key,
                        [a.__dict__ for a in scene.selected_media],
                        ttl=86400,
                    )

        self._logger.info(
            "Storyboard complete: %d scenes, %.1fs total",
            len(scenes),
            total_duration,
        )
        return Storyboard(script=script, scenes=scenes, total_duration=total_duration)

    def _download_asset(self, asset: MediaAsset, scene: Scene) -> str | None:
        try:
            output_dir = self._assets_dir / "storyboard"
            output_dir.mkdir(parents=True, exist_ok=True)
            ext = ".mp4" if asset.type == "video" else ".jpg"
            dest = output_dir / f"scene{scene.index}_{asset.provider}{ext}"
            if dest.exists():
                return str(dest)

            import requests
            resp = requests.get(asset.url, stream=True, timeout=30,
                                headers={"User-Agent": "ShortsAutomator/1.0"})
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return str(dest)
        except Exception as e:
            self._logger.warning("Download failed for %s: %s", asset.url, e)
            return None
