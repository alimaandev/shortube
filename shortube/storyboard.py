from __future__ import annotations

import abc
import json
import logging
import random
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

import requests

from shortube.config import get_settings
from shortube.types import MediaAsset, Scene, Script, Storyboard

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────

MIN_SCENE_DURATION: float = 1.5
SEARCH_TIMEOUT: float = 15.0
DOWNLOAD_TIMEOUT: float = 30.0
MAX_RETRIES: int = 3
RETRY_BACKOFF: float = 1.0
MAX_WORKERS_SEARCH: int = 12
MAX_WORKERS_DOWNLOAD: int = 6
USER_AGENT: str = "ShortsAutomator/2.0"


# ── Custom Exceptions ──────────────────────────────────────────────────


class StoryboardError(Exception):
    """Raised when storyboard generation fails irrecoverably."""


class MediaSearchError(Exception):
    """Raised when all media providers fail for a query."""


class DownloadError(Exception):
    """Raised when asset download fails after all retries."""


class AudioProbeError(Exception):
    """Raised when ffprobe cannot read the audio file."""


# ── Scene Builder ──────────────────────────────────────────────────────


@dataclass
class SceneBuilder:
    """Splits script text into timed scenes with natural grouping."""

    hook: str
    points: list[str]
    cta: str
    full_text: str
    total_duration: float

    def build(self) -> list[Scene]:
        """Create scenes by grouping narration around hook/points/cta."""
        sentences = self._split_sentences()
        groups = self._group_sentences(sentences)
        return self._create_scenes(groups)

    def _split_sentences(self) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+", self.full_text.strip())
        return [p.strip() for p in parts if p.strip()]

    def _group_sentences(self, sentences: list[str]) -> list[list[str]]:
        hook_words = set(self.hook.lower().split()[:5])
        cta_words = set(self.cta.lower().split()[:5])

        hook_group: list[str] = []
        cta_group: list[str] = []
        middle: list[str] = []

        for s in sentences:
            words = set(s.lower().split())
            if words & hook_words and not hook_group:
                hook_group.append(s)
            elif words & cta_words:
                cta_group.append(s)
            else:
                middle.append(s)

        if not hook_group and sentences:
            hook_group = [sentences[0]]
            middle = sentences[1:]
        if not cta_group and middle:
            cta_group = [middle.pop()]
        if not cta_group:
            cta_group = ["Thanks for watching!"]

        groups: list[list[str]] = [hook_group]
        n_points = max(len(self.points), 1)
        chunk_size = max(1, len(middle) // n_points)
        for i in range(n_points):
            start = i * chunk_size
            end = None if i == n_points - 1 else start + chunk_size
            groups.append(middle[start:end])
        groups.append(cta_group)
        return groups

    def _create_scenes(self, groups: list[list[str]]) -> list[Scene]:
        scenes: list[Scene] = []
        word_counts = [sum(len(s.split()) for s in g) for g in groups]
        total_words = max(sum(word_counts), 1)

        adjusted = []
        for i, wc in enumerate(word_counts):
            weight = wc / total_words
            if i == 0:
                weight *= 1.2
            adjusted.append(weight)

        adj_total = sum(adjusted)
        durations = [self.total_duration * (w / adj_total) for w in adjusted]
        durations = [max(d, MIN_SCENE_DURATION) for d in durations]

        dur_sum = sum(durations)
        if dur_sum > self.total_duration:
            scale = self.total_duration / dur_sum
            durations = [d * scale for d in durations]

        # Redistribute leftover time from clamped scenes
        leftover = self.total_duration - sum(durations)
        if leftover > 0 and durations:
            for i in range(len(durations)):
                add = leftover / len(durations)
                durations[i] += add

        current = 0.0
        for i, group in enumerate(groups):
            duration = durations[i] if i < len(durations) else MIN_SCENE_DURATION
            narration = " ".join(group)
            scenes.append(Scene(
                index=i,
                start_time=round(current, 3),
                end_time=round(current + duration, 3),
                narration=narration,
                visual_description=narration[:120],
            ))
            current += duration
        return scenes


# ── Media Providers ────────────────────────────────────────────────────


@dataclass
class SearchResult:
    """Normalised media asset from any provider."""
    url: str
    media_type: str  # "video" or "image"
    provider: str
    width: int
    height: int
    duration: float | None = None


class MediaProvider(abc.ABC):
    """Abstract base for stock media search providers."""

    @abc.abstractmethod
    def search_videos(self, query: str) -> list[SearchResult]:
        ...

    @abc.abstractmethod
    def search_images(self, query: str) -> list[SearchResult]:
        ...

    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...


class PexelsProvider(MediaProvider):
    """Pexels API video and image search."""

    VIDEO_URL: ClassVar[str] = "https://api.pexels.com/videos/search"
    IMAGE_URL: ClassVar[str] = "https://api.pexels.com/v1/search"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._headers = {"Authorization": api_key}
        self._session = requests.Session()

    @property
    def name(self) -> str:
        return "pexels"

    def search_videos(self, query: str) -> list[SearchResult]:
        try:
            resp = self._session.get(
                self.VIDEO_URL,
                headers=self._headers,
                params={"query": query, "per_page": 5, "orientation": "portrait"},
                timeout=SEARCH_TIMEOUT,
            )
            if resp.status_code != 200:
                logger.warning("Pexels video search returned %d", resp.status_code)
                return []
            results: list[SearchResult] = []
            for video in resp.json().get("videos", []):
                files = [
                    f for f in video.get("video_files", [])
                    if f.get("quality") in ("hd", "sd")
                ]
                if not files:
                    continue
                best = max(files, key=lambda f: f.get("width", 0) * f.get("height", 0))
                url = best.get("link")
                if url and video.get("duration", 0) >= MIN_SCENE_DURATION:
                    results.append(SearchResult(
                        url=url, media_type="video", provider=self.name,
                        width=video.get("width", 1080),
                        height=video.get("height", 1920),
                        duration=video.get("duration"),
                    ))
            return results
        except requests.RequestException as exc:
            logger.warning("Pexels video search failed: %s", exc)
            return []

    def search_images(self, query: str) -> list[SearchResult]:
        try:
            resp = self._session.get(
                self.IMAGE_URL,
                headers=self._headers,
                params={"query": query, "per_page": 5, "orientation": "portrait"},
                timeout=SEARCH_TIMEOUT,
            )
            if resp.status_code != 200:
                logger.warning("Pexels image search returned %d", resp.status_code)
                return []
            results: list[SearchResult] = []
            for photo in resp.json().get("photos", []):
                src = photo.get("src", {})
                url = (src.get("large2x") or src.get("large")
                       or src.get("medium") or src.get("original"))
                if url:
                    results.append(SearchResult(
                        url=url, media_type="image", provider=self.name,
                        width=photo.get("width", 1080),
                        height=photo.get("height", 1920),
                    ))
            return results
        except requests.RequestException as exc:
            logger.warning("Pexels image search failed: %s", exc)
            return []


class PixabayProvider(MediaProvider):
    """Pixabay API video and image search."""

    BASE_URL: ClassVar[str] = "https://pixabay.com/api/"
    HEADERS: ClassVar[dict[str, str]] = {"User-Agent": USER_AGENT}

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._session = requests.Session()

    @property
    def name(self) -> str:
        return "pixabay"

    def _params(self, **kwargs: Any) -> dict[str, Any]:
        params: dict[str, Any] = {
            "safesearch": "true",
            "orientation": "vertical",
        }
        if self._api_key:
            params["key"] = self._api_key
        params.update(kwargs)
        return params

    def search_videos(self, query: str) -> list[SearchResult]:
        try:
            resp = self._session.get(
                f"{self.BASE_URL}videos/",
                params=self._params(q=query, per_page=5),
                timeout=SEARCH_TIMEOUT,
                headers=self.HEADERS,
            )
            if resp.status_code != 200:
                logger.warning("Pixabay video search returned %d", resp.status_code)
                return []
            results: list[SearchResult] = []
            for hit in resp.json().get("hits", []):
                videos = hit.get("videos", {})
                for size in ("large", "medium", "small"):
                    info = videos.get(size)
                    if info:
                        results.append(SearchResult(
                            url=info["url"], media_type="video", provider=self.name,
                            width=info.get("width", 1080),
                            height=info.get("height", 1920),
                            duration=hit.get("duration"),
                        ))
                        break
            return results
        except requests.RequestException as exc:
            logger.warning("Pixabay video search failed: %s", exc)
            return []

    def search_images(self, query: str) -> list[SearchResult]:
        try:
            resp = self._session.get(
                self.BASE_URL,
                params=self._params(q=query, per_page=5, image_type="photo"),
                timeout=SEARCH_TIMEOUT,
                headers=self.HEADERS,
            )
            if resp.status_code != 200:
                logger.warning("Pixabay image search returned %d", resp.status_code)
                return []
            results: list[SearchResult] = []
            for hit in resp.json().get("hits", []):
                url = (hit.get("largeImageURL") or hit.get("webformatURL")
                       or hit.get("previewURL"))
                if url:
                    results.append(SearchResult(
                        url=url, media_type="image", provider=self.name,
                        width=hit.get("imageWidth", 1080),
                        height=hit.get("imageHeight", 1920),
                    ))
            return results
        except requests.RequestException as exc:
            logger.warning("Pixabay image search failed: %s", exc)
            return []


# ── Provider Registry ─────────────────────────────────────────────────


def _create_providers() -> list[MediaProvider]:
    """Instantiate all configured media providers."""
    cfg = get_settings()
    providers: list[MediaProvider] = []
    if cfg.pexels_api_key:
        providers.append(PexelsProvider(cfg.pexels_api_key))
    if cfg.pixabay_api_key:
        providers.append(PixabayProvider(cfg.pixabay_api_key))
    return providers


# ── Media Search Service ───────────────────────────────────────────────


class MediaSearchService:
    """Orchestrates concurrent media search across all providers."""

    def __init__(self, providers: list[MediaProvider]) -> None:
        self._providers = providers

    def search(self, queries: list[str]) -> list[SearchResult]:
        """Search all providers for all queries concurrently."""
        seen: set[str] = set()
        all_results: list[SearchResult] = []

        with ThreadPoolExecutor(max_workers=MAX_WORKERS_SEARCH) as pool:
            futures = []
            for q in queries:
                for provider in self._providers:
                    futures.append(pool.submit(provider.search_videos, q))
                    futures.append(pool.submit(provider.search_images, q))

            for future in as_completed(futures):
                for result in future.result():
                    if result.url not in seen:
                        seen.add(result.url)
                        all_results.append(result)

        logger.info(
            "Search complete: %d unique assets from %d queries across %d providers",
            len(all_results), len(queries), len(self._providers),
        )
        return all_results


# ── Asset Ranking ──────────────────────────────────────────────────────


class AssetRanker:
    """Ranks and filters media assets by quality and type."""

    def rank(self, assets: list[SearchResult]) -> list[SearchResult]:
        """Sort assets: videos before images, then by portrait orientation."""
        def sort_key(a: SearchResult) -> tuple[int, int]:
            # Videos first (0), then images (1)
            type_rank = 0 if a.media_type == "video" else 1
            # Prefer portrait (9:16) orientation
            if a.width > 0 and a.height > 0:
                aspect = a.height / a.width
                portrait_score = abs(aspect - 16 / 9)
            else:
                portrait_score = 999
            return (type_rank, portrait_score)
        return sorted(assets, key=sort_key)

    def deduplicate(self, assets: list[SearchResult]) -> list[SearchResult]:
        """Remove entries with identical URLs, keeping first occurrence."""
        seen: set[str] = set()
        unique: list[SearchResult] = []
        for a in assets:
            if a.url not in seen:
                seen.add(a.url)
                unique.append(a)
        return unique

    def distribute(
        self,
        assets: list[SearchResult],
        n_scenes: int,
        assets_per_scene: int = 2,
    ) -> list[list[SearchResult]]:
        """Distribute assets evenly across scenes with variety."""
        videos = [a for a in assets if a.media_type == "video"]
        images = [a for a in assets if a.media_type == "image"]
        random.shuffle(videos)
        random.shuffle(images)

        scene_assets: list[list[SearchResult]] = [[] for _ in range(n_scenes)]

        # Each scene gets 1 video if available
        for i in range(n_scenes):
            if i < len(videos):
                scene_assets[i].append(videos[i])

        # Fill remaining slots with images then remaining videos
        remaining = [a for a in images]
        remaining += [a for a in videos[len(videos) % n_scenes:]]

        for i in range(n_scenes):
            while len(scene_assets[i]) < assets_per_scene and remaining:
                scene_assets[i].append(remaining.pop(0))

        return scene_assets


# ── Download Manager ───────────────────────────────────────────────────


class DownloadManager:
    """Manages concurrent downloads with caching and retry logic."""

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_index = self._load_cache_index()
        self._session = requests.Session()

    def _load_cache_index(self) -> dict[str, str]:
        path = self._cache_dir / "_index.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_cache_index(self) -> None:
        path = self._cache_dir / "_index.json"
        path.write_text(
            json.dumps(self._cache_index, indent=2),
            encoding="utf-8",
        )

    def _asset_path(self, url: str, media_type: str) -> Path:
        ext = ".mp4" if media_type == "video" else ".jpg"
        return self._cache_dir / f"{abs(hash(url)):x}{ext}"

    def get(self, url: str, media_type: str) -> str | None:
        """Return local path for asset, downloading if not cached."""
        cached = self._cache_index.get(url)
        if cached:
            cached_path = Path(cached)
            if cached_path.exists() and cached_path.stat().st_size > 0:
                logger.debug("Cache hit: %s", url[:60])
                return str(cached_path)
            logger.debug("Cache stale, re-downloading: %s", url[:60])

        dest = self._asset_path(url, media_type)
        for attempt in range(MAX_RETRIES):
            try:
                resp = self._session.get(
                    url, stream=True,
                    timeout=DOWNLOAD_TIMEOUT,
                    headers={"User-Agent": USER_AGENT},
                )
                resp.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            except (requests.RequestException, OSError) as exc:
                logger.warning(
                    "Download attempt %d/%d failed for %s: %s",
                    attempt + 1, MAX_RETRIES, url[:60], exc,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF * (2 ** attempt))
                continue

            if dest.exists() and dest.stat().st_size > 0:
                self._cache_index[url] = str(dest)
                self._save_cache_index()
                logger.debug("Downloaded: %s -> %s", url[:60], dest.name)
                return str(dest)

            logger.warning("Downloaded file empty for %s, retrying", url[:60])

        logger.error("Download failed after %d attempts: %s", MAX_RETRIES, url[:60])
        return None

    def download_all(
        self,
        assets: list[SearchResult],
    ) -> dict[str, str]:
        """Download multiple assets concurrently. Returns url -> local_path map."""
        url_to_path: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS_DOWNLOAD) as pool:
            future_map = {
                pool.submit(self.get, a.url, a.media_type): a.url
                for a in assets
            }
            for future in as_completed(future_map):
                url = future_map[future]
                try:
                    path = future.result()
                    if path:
                        url_to_path[url] = path
                except Exception as exc:
                    logger.warning("Unexpected download error for %s: %s", url[:60], exc)
        logger.info(
            "Downloaded %d/%d assets successfully",
            len(url_to_path), len(assets),
        )
        return url_to_path


# ── Audio Probe ────────────────────────────────────────────────────────


def get_audio_duration(path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise AudioProbeError(
                f"ffprobe returned {result.returncode}: {result.stderr.strip()}"
            )
        duration = float(result.stdout.strip())
        if duration <= 0:
            raise AudioProbeError(f"Invalid audio duration: {duration}")
        return duration
    except FileNotFoundError as exc:
        raise AudioProbeError("ffprobe not found. Install FFmpeg.") from exc
    except ValueError as exc:
        raise AudioProbeError(f"Could not parse ffprobe output: {exc}") from exc
    except subprocess.TimeoutExpired:
        raise AudioProbeError("ffprobe timed out") from None


# ── Public API ─────────────────────────────────────────────────────────


@dataclass
class StoryboardGenerator:
    """Orchestrates the full storyboard pipeline."""

    script: Script
    voiceover_path: str

    def run(self) -> Storyboard:
        """Execute the storyboard pipeline and return a Storyboard."""
        logger.info("Starting storyboard generation for: %s", self.script.topic[:60])

        # 1. Get audio duration
        total_duration = get_audio_duration(self.voiceover_path)
        logger.info("Audio duration: %.2fs", total_duration)

        # 2. Build scenes
        builder = SceneBuilder(
            hook=self.script.hook,
            points=self.script.points,
            cta=self.script.cta,
            full_text=self.script.full_text,
            total_duration=total_duration,
        )
        scenes = builder.build()
        logger.info("Created %d scenes", len(scenes))

        # 3. Search for media
        providers = _create_providers()
        if not providers:
            logger.warning("No media providers configured (no API keys)")
            return Storyboard(script=self.script, scenes=scenes,
                              total_duration=total_duration)

        # Vary search queries to get diverse results
        search_queries = list(dict.fromkeys(self.script.keywords + [self.script.topic]))
        modifiers = [
            "", "background", "nature", "urban", "people", "technology",
            "abstract", "business", "science", "art", "design", "motion",
            "action", "scene", "aerial", "closeup",
        ]
        search_queries = [
            f"{q} {random.choice(modifiers)}" if random.random() > 0.3 else q
            for q in search_queries
        ]

        search_service = MediaSearchService(providers)
        raw_assets = search_service.search(search_queries)

        # 4. Rank and filter
        ranker = AssetRanker()
        ranked = ranker.deduplicate(raw_assets)
        ranked = ranker.rank(ranked)

        if not ranked:
            logger.warning("No media assets found, continuing with empty scenes")
            return Storyboard(script=self.script, scenes=scenes,
                              total_duration=total_duration)

        # 5. Distribute assets to scenes
        distributed = ranker.distribute(ranked, len(scenes), assets_per_scene=2)

        # 6. Download assets
        cfg = get_settings()
        assets_dir = cfg.base_dir / "output" / ".assets"
        downloader = DownloadManager(assets_dir)

        all_assets_to_dl: list[SearchResult] = []
        flat_distributed: list[tuple[int, SearchResult]] = []
        for scene_idx, asset_list in enumerate(distributed):
            for asset in asset_list:
                all_assets_to_dl.append(asset)
                flat_distributed.append((scene_idx, asset))

        url_map = downloader.download_all(all_assets_to_dl)

        # 7. Assign downloaded paths to scenes
        for scene_idx, asset in flat_distributed:
            local_path = url_map.get(asset.url)
            if local_path:
                scenes[scene_idx].selected_media.append(MediaAsset(
                    url=asset.url,
                    type=asset.media_type,  # type: ignore[arg-type]
                    provider=asset.provider,
                    width=asset.width,
                    height=asset.height,
                    duration=asset.duration,
                    local_path=local_path,
                ))

        downloaded_count = sum(1 for s in scenes if s.selected_media)
        logger.info(
            "Storyboard complete: %d scenes, %.1fs, %d scenes have media",
            len(scenes), total_duration, downloaded_count,
        )
        return Storyboard(script=self.script, scenes=scenes,
                          total_duration=total_duration)


def generate_storyboard(script: Script, voiceover_path: str) -> Storyboard:
    """Generate a full storyboard with scenes and media assets.

    Args:
        script: The Script object with hook, points, cta, full_text, keywords.
        voiceover_path: Path to the generated voiceover audio file.

    Returns:
        A Storyboard with timed scenes and downloaded media assets.

    Raises:
        StoryboardError: If the audio file cannot be probed.
    """
    generator = StoryboardGenerator(script=script, voiceover_path=voiceover_path)
    return generator.run()
