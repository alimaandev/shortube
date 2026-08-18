from __future__ import annotations

import json
import logging
import os
import random
import re
import time
import urllib.parse
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import requests
from PIL import Image, ImageDraw, ImageFont

from shortube.config import get_settings
from shortube.types import MediaAsset, Scene, Script, Storyboard

logger = logging.getLogger(__name__)

MIN_SCENE_DURATION: float = 1.5
DOWNLOAD_TIMEOUT: float = 60.0
MAX_RETRIES: int = 3
RETRY_BACKOFF: float = 1.0
DOWNLOAD_DELAY: tuple[float, float] = (0.5, 1.5)
USER_AGENT: str = "ShortsAutomator/2.0"
MIN_MEDIA_COUNT: int = 2

# Media size caps: bounds decode memory in Remotion and avoids junk assets.
MAX_IMAGE_BYTES: int = 25 * 1024 * 1024
MAX_VIDEO_BYTES: int = 250 * 1024 * 1024
MAX_IMAGE_DIMENSION: int = 2560


class StoryboardError(Exception):
    pass


class AudioProbeError(Exception):
    pass


_STOPWORDS: set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could", "this", "that",
    "these", "those", "it", "its", "they", "them", "their", "we", "our",
    "you", "your", "he", "she", "him", "her", "his", "my", "me", "i",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "because", "but", "and", "or", "if", "while", "although",
    "about", "up", "down",
}


def _extract_keywords(text: str, niche: str = "", max_words: int = 5) -> list[str]:
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    meaningful = [w for w in words if w not in _STOPWORDS]
    unique = list(dict.fromkeys(sorted(meaningful, key=len, reverse=True)))
    result = unique[:max_words]
    if niche:
        result.append(niche)
    return result[:max_words]


# ── Scene Builder ──────────────────────────────────────────────────────


@dataclass
class SceneBuilder:
    hook: str
    points: list[str]
    cta: str
    full_text: str
    total_duration: float
    niche: str = ""

    def build(self) -> list[Scene]:
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
        leftover = self.total_duration - sum(durations)
        if leftover > 0 and durations:
            for i in range(len(durations)):
                durations[i] += leftover / len(durations)
        current = 0.0
        for i, group in enumerate(groups):
            duration = durations[i] if i < len(durations) else MIN_SCENE_DURATION
            narration = " ".join(group)
            keywords = _extract_keywords(narration, self.niche)
            scenes.append(Scene(
                index=i,
                start_time=round(current, 3),
                end_time=round(current + duration, 3),
                narration=narration,
                visual_description=narration[:120],
                search_queries=keywords,
            ))
            current += duration
        return scenes


# ── Abstract Media Provider ────────────────────────────────────────────


class MediaProvider(ABC):
    @abstractmethod
    def search(self, query: str, count: int = 3) -> list[dict]:
        ...


# ── Pexels Video Provider ──────────────────────────────────────────────


class PexelsVideoProvider(MediaProvider):
    API_URL = "https://api.pexels.com/videos/search"

    def search(self, query: str, count: int = 3) -> list[dict]:
        cfg = get_settings()
        api_key = cfg.pexels_api_key
        if not api_key:
            logger.debug("Pexels API key not configured")
            return []

        try:
            resp = requests.get(
                self.API_URL,
                params={"query": query, "per_page": count, "orientation": "portrait", "size": "medium"},
                headers={"Authorization": api_key, "User-Agent": USER_AGENT},
                timeout=15,
            )
            if resp.status_code == 429:
                logger.warning("Pexels rate limited (429)")
                return []
            resp.raise_for_status()
            data = resp.json()
            results: list[dict] = []
            for video in data.get("videos", []):
                for file in video.get("video_files", []):
                    if (
                        file.get("width", 0) >= 720
                        and file.get("quality") == "hd"
                        and file.get("file_type") == "video/mp4"
                        and file.get("link")
                    ):
                        results.append({
                            "url": file["link"],
                            "width": file.get("width", 1080),
                            "height": file.get("height", 1920),
                            "type": "video",
                            "provider": "pexels",
                            "duration": video.get("duration"),
                            "thumbnail": (video.get("image") or ""),
                        })
                        break
            logger.info("Pexels videos: found %d for '%s'", len(results), query[:40])
            return results
        except requests.RequestException as e:
            logger.warning("Pexels video search failed: %s", e)
            return []


class PexelsImageProvider(MediaProvider):
    API_URL = "https://api.pexels.com/v1/search"

    def search(self, query: str, count: int = 3) -> list[dict]:
        cfg = get_settings()
        api_key = cfg.pexels_api_key
        if not api_key:
            return []

        try:
            resp = requests.get(
                self.API_URL,
                params={"query": query, "per_page": count, "orientation": "portrait"},
                headers={"Authorization": api_key, "User-Agent": USER_AGENT},
                timeout=15,
            )
            if resp.status_code == 429:
                logger.warning("Pexels images rate limited (429)")
                return []
            resp.raise_for_status()
            data = resp.json()
            results: list[dict] = []
            for photo in data.get("photos", []):
                src = photo.get("src", {})
                url = src.get("large2x") or src.get("large") or src.get("original")
                if url:
                    results.append({
                        "url": url,
                        "width": photo.get("width", 1080),
                        "height": photo.get("height", 1920),
                        "type": "image",
                        "provider": "pexels",
                        "duration": None,
                        "thumbnail": src.get("tiny", ""),
                    })
            logger.info("Pexels images: found %d for '%s'", len(results), query[:40])
            return results
        except requests.RequestException as e:
            logger.warning("Pexels image search failed: %s", e)
            return []


# ── Pixabay Video Provider ─────────────────────────────────────────────


class PixabayVideoProvider(MediaProvider):
    API_URL = "https://pixabay.com/api/videos"

    def search(self, query: str, count: int = 3) -> list[dict]:
        cfg = get_settings()
        api_key = cfg.pixabay_api_key
        if not api_key:
            logger.debug("Pixabay API key not configured")
            return []

        try:
            resp = requests.get(
                self.API_URL,
                params={"key": api_key, "q": query, "per_page": count, "orientation": "vertical", "safesearch": "true"},
                timeout=15,
            )
            if resp.status_code == 429:
                logger.warning("Pixabay rate limited (429)")
                return []
            resp.raise_for_status()
            data = resp.json()
            results: list[dict] = []
            for hit in data.get("hits", []):
                videos = hit.get("videos", {})
                for quality in ["large", "medium", "small"]:
                    v = videos.get(quality)
                    if v and v.get("url"):
                        results.append({
                            "url": v["url"],
                            "width": v.get("width", 1080),
                            "height": v.get("height", 1920),
                            "type": "video",
                            "provider": "pixabay",
                            "duration": hit.get("duration"),
                            "thumbnail": (hit.get("pageURL") or ""),
                        })
                        break
            logger.info("Pixabay videos: found %d for '%s'", len(results), query[:40])
            return results
        except requests.RequestException as e:
            logger.warning("Pixabay video search failed: %s", e)
            return []


class PixabayImageProvider(MediaProvider):
    API_URL = "https://pixabay.com/api"

    def search(self, query: str, count: int = 3) -> list[dict]:
        cfg = get_settings()
        api_key = cfg.pixabay_api_key
        if not api_key:
            return []

        try:
            resp = requests.get(
                self.API_URL,
                params={
                    "key": api_key, "q": query, "per_page": count,
                    "orientation": "vertical", "safesearch": "true",
                    "image_type": "photo",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            results: list[dict] = []
            for hit in data.get("hits", []):
                url = hit.get("largeImageURL") or hit.get("webformatURL")
                if url:
                    results.append({
                        "url": url,
                        "width": hit.get("imageWidth", 1080),
                        "height": hit.get("imageHeight", 1920),
                        "type": "image",
                        "provider": "pixabay",
                        "duration": None,
                        "thumbnail": hit.get("previewURL", ""),
                    })
            logger.info("Pixabay images: found %d for '%s'", len(results), query[:40])
            return results
        except requests.RequestException as e:
            logger.warning("Pixabay image search failed: %s", e)
            return []


# ── Pollinations Provider (unchanged logic, adapted to interface) ─────


class PollinationsProvider(MediaProvider):
    BASE_URL: ClassVar[str] = "https://image.pollinations.ai/prompt"
    STYLE: ClassVar[str] = (
        "cinematic photography, professional lighting, "
        "highly detailed, sharp focus, 8k, photorealistic"
    )

    def search(self, query: str, count: int = 3) -> list[dict]:
        results: list[dict] = []
        for i in range(count):
            seed = random.randint(0, 99999) + i * 7
            full = f"{query[:200]}, {self.STYLE}"
            encoded = urllib.parse.quote(full)
            url = (
                f"{self.BASE_URL}/{encoded}"
                f"?model=flux&width=1080&height=1920&nologo=true&seed={seed}"
            )
            results.append({
                "url": url,
                "width": 1080,
                "height": 1920,
                "type": "image",
                "provider": "pollinations",
                "duration": None,
                "thumbnail": "",
            })
        logger.debug("Pollinations: prepared %d URLs for '%s'", len(results), query[:40])
        return results


# ── Fallback: Text-on-Gradient Image Generator ─────────────────────────


def _generate_fallback_image(
    text: str,
    output_dir: Path,
    scene_index: int,
    width: int = 1080,
    height: int = 1920,
) -> str:
    img = Image.new("RGB", (width, height))
    for y in range(height):
        r = int(20 + (y / height) * 30)
        g = int(20 + (y / height) * 50)
        b = int(40 + (y / height) * 30)
        for x in range(width):
            img.putpixel((x, y), (r, g, b))

    draw = ImageDraw.Draw(img)
    font_size = 48
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        try:
            font = ImageFont.truetype("C:\\Windows\\Fonts\\segoeui.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

    max_w = width - 120
    lines: list[str] = []
    for word in text.split():
        if not lines:
            lines.append(word)
        else:
            test = f"{lines[-1]} {word}"
            try:
                bbox = draw.textbbox((0, 0), test, font=font)
            except (AttributeError, TypeError):
                bbox = (0, 0, 0, 0)
            if bbox[2] - bbox[0] <= max_w:
                lines[-1] = test
            else:
                lines.append(word)

    line_height = font_size + 12
    total_h = len(lines) * line_height
    start_y = (height - total_h) // 2

    for i, line in enumerate(lines):
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_w = bbox[2] - bbox[0]
        except (AttributeError, TypeError):
            line_w = len(line) * font_size // 2
        x = (width - line_w) // 2
        y = start_y + i * line_height
        draw.text((x + 2, y + 2), line, fill=(0, 0, 0), font=font)
        draw.text((x, y), line, fill=(255, 255, 255), font=font)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"fallback_{scene_index}.jpg"
    img.save(str(out_path), "JPEG", quality=85)
    logger.info("Generated fallback text image: %s", out_path.name)
    return str(out_path)


# ── Media Provider Chain ───────────────────────────────────────────────


_PROVIDER_REGISTRY: dict[str, type[MediaProvider]] = {
    "pexels_video": PexelsVideoProvider,
    "pixabay_video": PixabayVideoProvider,
    "pexels_image": PexelsImageProvider,
    "pixabay_image": PixabayImageProvider,
    "pollinations": PollinationsProvider,
}


def _get_provider_chain(cfg) -> list[MediaProvider]:
    mode = cfg.image_provider
    if mode == "pollinations":
        return [PollinationsProvider()]
    if mode == "pexels":
        return [PexelsVideoProvider(), PexelsImageProvider(), PollinationsProvider()]
    if mode == "pixabay":
        return [PixabayVideoProvider(), PixabayImageProvider(), PollinationsProvider()]
    return [
        PexelsVideoProvider(),
        PixabayVideoProvider(),
        PexelsImageProvider(),
        PixabayImageProvider(),
        PollinationsProvider(),
    ]


# ── Download Manager (extended for video) ──────────────────────────────


class DownloadManager:
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
        (self._cache_dir / "_index.json").write_text(
            json.dumps(self._cache_index, indent=2), encoding="utf-8",
        )

    def _local_path(self, url: str, ext: str = ".jpg") -> Path:
        h = f"{abs(hash(url)):x}"
        return self._cache_dir / f"{h}{ext}"

    def _validate_file(self, path: Path, media_type: str) -> bool:
        if not path.exists():
            return False
        size = path.stat().st_size
        if size < 2000:
            return False
        if media_type == "image":
            if size > MAX_IMAGE_BYTES:
                logger.warning("Image exceeds size cap (%d bytes): %s", MAX_IMAGE_BYTES, path.name)
                return False
            try:
                from PIL import Image
                with Image.open(path) as img:
                    img.verify()
                return True
            except Exception:
                return False
        if media_type == "video":
            return 5000 < size <= MAX_VIDEO_BYTES
        return True

    def _downscale_image(self, path: Path) -> Path:
        """Shrink oversized images so Remotion decodes them cheaply.

        Returns the final on-disk path (unchanged unless scaled).
        """
        try:
            from PIL import Image
            with Image.open(path) as img:
                w, h = img.size
                if w <= MAX_IMAGE_DIMENSION and h <= MAX_IMAGE_DIMENSION:
                    return path
                resample = getattr(Image, "Resampling", Image).LANCZOS
                img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), resample)
                tmp = path.with_name(path.stem + "_scaled.jpg")
                img.convert("RGB").save(str(tmp), "JPEG", quality=85)
            os.replace(tmp, path)
            logger.info(
                "Downscaled image %s to fit %dx%d", path.name,
                MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION,
            )
        except Exception as e:
            logger.warning("Image downscale failed for %s: %s", path.name, e)
        return path

    def get(self, url: str, media_type: str = "image") -> str | None:
        cached = self._cache_index.get(url)
        if cached:
            p = Path(cached)
            if self._validate_file(p, media_type):
                return str(p)

        ext = ".mp4" if media_type == "video" else ".jpg"
        dest = self._local_path(url, ext)
        max_bytes = MAX_VIDEO_BYTES if media_type == "video" else MAX_IMAGE_BYTES

        for attempt in range(MAX_RETRIES):
            try:
                resp = self._session.get(
                    url, stream=True, timeout=DOWNLOAD_TIMEOUT,
                    headers={"User-Agent": USER_AGENT},
                )
                if resp.status_code == 429:
                    wait = (2 ** attempt) * 5.0
                    logger.warning("Rate limited (429), waiting %.0fs...", wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()

                content_type = resp.headers.get("Content-Type", "")
                if media_type == "image" and "image" not in content_type:
                    logger.warning("Unexpected Content-Type: %s", content_type)
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_BACKOFF * (2 ** attempt))
                    continue

                content_length = resp.headers.get("Content-Length")
                if content_length and int(content_length) > max_bytes:
                    logger.warning(
                        "Rejecting oversized %s (%s bytes > %d cap)",
                        media_type, content_length, max_bytes,
                    )
                    dest.unlink(missing_ok=True)
                    return None

                total = 0
                aborted = False
                with open(dest, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=32768):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > max_bytes:
                            aborted = True
                            break
                        f.write(chunk)
                if aborted:
                    logger.warning(
                        "%s exceeded %d byte cap during download — aborting",
                        media_type, max_bytes,
                    )
                    dest.unlink(missing_ok=True)
                    return None

                if self._validate_file(dest, media_type):
                    final = dest
                    if media_type == "image":
                        final = self._downscale_image(dest)
                    self._cache_index[url] = str(final)
                    self._save_cache_index()
                    return str(final)
            except (requests.RequestException, OSError) as exc:
                logger.warning(
                    "Download attempt %d/%d failed: %s",
                    attempt + 1, MAX_RETRIES, exc,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF * (2 ** attempt))
        logger.error("Download failed after %d attempts: %s", MAX_RETRIES, url[:80])
        return None


# ── Audio Probe ────────────────────────────────────────────────────────


def get_audio_duration(path: str) -> float:
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(path)
        duration = audio.duration_seconds
        if duration <= 0:
            raise AudioProbeError(f"Invalid duration: {duration}")
        return duration
    except Exception as exc:
        raise AudioProbeError(f"Failed to get audio duration: {exc}") from exc


# ── Public API ─────────────────────────────────────────────────────────


@dataclass
class StoryboardGenerator:
    script: Script
    voiceover_path: str

    def run(self) -> Storyboard:
        logger.info("Generating storyboard for: %s", self.script.topic[:60])

        total_duration = get_audio_duration(self.voiceover_path)
        logger.info("Audio: %.2fs", total_duration)

        cfg = get_settings()
        builder = SceneBuilder(
            hook=self.script.hook, points=self.script.points,
            cta=self.script.cta, full_text=self.script.full_text,
            total_duration=total_duration, niche=cfg.niche,
        )
        scenes = builder.build()
        logger.info("Scenes: %d", len(scenes))

        downloader = DownloadManager(cfg.base_dir / "output" / ".assets")
        provider_chain = _get_provider_chain(cfg)
        fallback_dir = cfg.base_dir / "output" / ".fallback"

        for scene in scenes:
            query = " ".join(scene.search_queries) if scene.search_queries else scene.visual_description[:100]
            logger.debug("Scene %d search: '%s'", scene.index, query[:60])

            found_any = False

            for provider_cls in provider_chain:
                try:
                    results = provider_cls.search(query, count=MIN_MEDIA_COUNT)
                except Exception as e:
                    logger.warning("Provider %s failed: %s", type(provider_cls).__name__, e)
                    continue

                for item in results:
                    media_type = item.get("type", "image")
                    local_path = downloader.get(item["url"], media_type=media_type)
                    if local_path:
                        asset = MediaAsset(
                            url=item["url"],
                            type=media_type,
                            provider=item.get("provider", "unknown"),
                            width=item.get("width", 1080),
                            height=item.get("height", 1920),
                            local_path=local_path,
                            duration=item.get("duration"),
                        )
                        scene.selected_media.append(asset)
                        found_any = True

                if found_any:
                    break

            if not found_any:
                logger.warning("Scene %d has no media — generating fallback text image", scene.index)
                fallback_path = _generate_fallback_image(scene.narration, fallback_dir, scene.index)
                asset = MediaAsset(
                    url="",
                    type="image",
                    provider="fallback",
                    width=1080,
                    height=1920,
                    local_path=fallback_path,
                )
                scene.selected_media.append(asset)

        scenes_with_media = sum(1 for s in scenes if s.selected_media)
        total_assets = sum(len(s.selected_media) for s in scenes)
        logger.info(
            "Storyboard done: %d scenes, %.1fs, %d with media (%d total assets)",
            len(scenes), total_duration, scenes_with_media, total_assets,
        )

        return Storyboard(script=self.script, scenes=scenes, total_duration=total_duration)


def generate_storyboard(script: Script, voiceover_path: str) -> Storyboard:
    generator = StoryboardGenerator(script=script, voiceover_path=voiceover_path)
    return generator.run()
