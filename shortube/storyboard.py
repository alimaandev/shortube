from __future__ import annotations

import json
import logging
import random
import re
import subprocess
import time

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import requests

from shortube.config import get_settings
from shortube.types import MediaAsset, Scene, Script, Storyboard

logger = logging.getLogger(__name__)

MIN_SCENE_DURATION: float = 1.5
DOWNLOAD_TIMEOUT: float = 60.0
MAX_RETRIES: int = 3
RETRY_BACKOFF: float = 1.0
DOWNLOAD_DELAY: tuple[float, float] = (1.5, 3.0)
USER_AGENT: str = "ShortsAutomator/2.0"


class StoryboardError(Exception):
    pass


class AudioProbeError(Exception):
    pass


# ── Scene Builder ──────────────────────────────────────────────────────


@dataclass
class SceneBuilder:
    hook: str
    points: list[str]
    cta: str
    full_text: str
    total_duration: float

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
            scenes.append(Scene(
                index=i,
                start_time=round(current, 3),
                end_time=round(current + duration, 3),
                narration=narration,
                visual_description=narration[:120],
            ))
            current += duration
        return scenes


# ── Pollinations AI Provider ───────────────────────────────────────────


class PollinationsProvider:
    """Generates scene images via Pollinations.ai (free, no API key)."""

    BASE_URL: ClassVar[str] = "https://image.pollinations.ai/prompt"
    STYLE: ClassVar[str] = (
        "cinematic photography, professional lighting, "
        "highly detailed, sharp focus, 8k, photorealistic"
    )

    def generate_url(self, prompt: str, seed: int) -> str:
        """Build a Pollinations image URL. The image is generated on first GET."""
        import urllib.parse
        full = f"{prompt}, {self.STYLE}"
        encoded = urllib.parse.quote(full)
        return (
            f"{self.BASE_URL}/{encoded}"
            f"?model=flux&width=1080&height=1920&nologo=true&seed={seed}"
        )

    def generate_scene_images(self, scenes: list[Scene]) -> list[dict]:
        """Build one Pollinations image URL per scene using narration as prompt."""
        results: list[dict] = []
        for scene in scenes:
            prompt = (scene.narration or scene.visual_description or "cinematic landscape")[:200]
            url = self.generate_url(prompt, seed=scene.index * 7 + 42)
            results.append({
                "url": url,
                "scene_index": scene.index,
            })
        logger.info("Prepared %d scene image URLs via Pollinations", len(results))
        return results


# ── Download Manager ───────────────────────────────────────────────────


class DownloadManager:
    """Downloads files with caching and retry."""

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

    def _local_path(self, url: str) -> Path:
        return self._cache_dir / f"{abs(hash(url)):x}.jpg"

    def get(self, url: str) -> str | None:
        cached = self._cache_index.get(url)
        if cached:
            p = Path(cached)
            if p.exists() and p.stat().st_size > 0:
                return str(p)

        dest = self._local_path(url)
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
                with open(dest, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                if dest.exists() and dest.stat().st_size > 1000:
                    self._cache_index[url] = str(dest)
                    self._save_cache_index()
                    return str(dest)
            except (requests.RequestException, OSError) as exc:
                logger.warning(
                    "Download attempt %d/%d failed: %s",
                    attempt + 1, MAX_RETRIES, exc,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF * (2 ** attempt))
        logger.error("Download failed after %d attempts", MAX_RETRIES)
        return None

    def download_all(self, urls: list[str]) -> dict[str, str]:
        """Download URLs sequentially with delays to avoid rate limits."""
        result: dict[str, str] = {}
        for i, url in enumerate(urls):
            if i > 0:
                time.sleep(random.uniform(*DOWNLOAD_DELAY))
            try:
                path = self.get(url)
                if path:
                    result[url] = path
            except Exception as exc:
                logger.warning("Download error for %s: %s", url[:60], exc)
        logger.info("Downloaded %d/%d files", len(result), len(urls))
        return result


# ── Audio Probe ────────────────────────────────────────────────────────


def get_audio_duration(path: str) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise AudioProbeError(f"ffprobe error: {result.stderr.strip()}")
        duration = float(result.stdout.strip())
        if duration <= 0:
            raise AudioProbeError(f"Invalid duration: {duration}")
        return duration
    except FileNotFoundError as exc:
        raise AudioProbeError("ffprobe not found. Install FFmpeg.") from exc
    except ValueError as exc:
        raise AudioProbeError(f"Bad ffprobe output: {exc}") from exc
    except subprocess.TimeoutExpired:
        raise AudioProbeError("ffprobe timed out") from None


# ── Public API ─────────────────────────────────────────────────────────


@dataclass
class StoryboardGenerator:
    script: Script
    voiceover_path: str

    def run(self) -> Storyboard:
        logger.info("Generating storyboard for: %s", self.script.topic[:60])

        # 1. Audio duration
        total_duration = get_audio_duration(self.voiceover_path)
        logger.info("Audio: %.2fs", total_duration)

        # 2. Build scenes
        builder = SceneBuilder(
            hook=self.script.hook, points=self.script.points,
            cta=self.script.cta, full_text=self.script.full_text,
            total_duration=total_duration,
        )
        scenes = builder.build()
        logger.info("Scenes: %d", len(scenes))

        # 3. Generate Pollinations image URLs per scene
        pollinations = PollinationsProvider()
        scene_images = pollinations.generate_scene_images(scenes)

        if not scene_images:
            logger.warning("No scene images generated")
            return Storyboard(script=self.script, scenes=scenes,
                              total_duration=total_duration)

        # 4. Download all images concurrently
        cfg = get_settings()
        downloader = DownloadManager(cfg.base_dir / "output" / ".assets")
        urls = [item["url"] for item in scene_images]
        url_map = downloader.download_all(urls)

        # 5. Assign downloaded images to scenes
        for item in scene_images:
            local_path = url_map.get(item["url"])
            if local_path:
                scenes[item["scene_index"]].selected_media.append(MediaAsset(
                    url=item["url"], type="image", provider="pollinations",
                    width=1080, height=1920, local_path=local_path,
                ))

        scenes_with = sum(1 for s in scenes if s.selected_media)
        logger.info(
            "Storyboard done: %d scenes, %.1fs, %d with images",
            len(scenes), total_duration, scenes_with,
        )
        return Storyboard(script=self.script, scenes=scenes,
                          total_duration=total_duration)


def generate_storyboard(script: Script, voiceover_path: str) -> Storyboard:
    generator = StoryboardGenerator(script=script, voiceover_path=voiceover_path)
    return generator.run()
