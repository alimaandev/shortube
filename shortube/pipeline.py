from __future__ import annotations

import json
import logging
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from shortube.assemble import AssemblyError, assemble_video
from shortube.config import get_settings
from shortube.db import Database, VideoRow
from shortube.remotion_bridge import RemotionError
from shortube.script import generate_script
from shortube.storyboard import generate_storyboard
from shortube.types import Script, Storyboard
from shortube.upload import generate_thumbnail, upload_script
from shortube.voice import generate_voiceover

logger = logging.getLogger(__name__)


class DependencyError(Exception):
    pass


class PipelineError(Exception):
    pass


class PipelineCancelled(Exception):
    """Raised when the user cancels a running job."""


class Stage(StrEnum):
    SCRIPT = "script"
    VOICEOVER = "voiceover"
    STORYBOARD = "storyboard"
    ASSEMBLE = "assemble"
    THUMBNAIL = "thumbnail"
    UPLOAD = "upload"


STAGE_LABELS: dict[Stage, str] = {
    Stage.SCRIPT: "Generating script...",
    Stage.VOICEOVER: "Generating voiceover...",
    Stage.STORYBOARD: "Generating storyboard with AI images...",
    Stage.ASSEMBLE: "Assembling video...",
    Stage.THUMBNAIL: "Generating thumbnail...",
    Stage.UPLOAD: "Uploading to YouTube...",
}

STAGE_PERCENT: dict[Stage, int] = {
    Stage.SCRIPT: 5,
    Stage.VOICEOVER: 25,
    Stage.STORYBOARD: 45,
    Stage.ASSEMBLE: 65,
    Stage.THUMBNAIL: 90,
    Stage.UPLOAD: 94,
}


@dataclass(frozen=True)
class StageEvent:
    """Typed progress event emitted at each pipeline stage boundary."""

    stage: Stage

    @property
    def message(self) -> str:
        return STAGE_LABELS[self.stage]

    @property
    def percent(self) -> int:
        return STAGE_PERCENT[self.stage]


class CancelToken:
    """Thread-safe cancellation signal checked between pipeline stages."""

    def __init__(self, event: threading.Event | None = None) -> None:
        self._event = event or threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        """Raise PipelineCancelled if cancellation was requested."""
        if self._event.is_set():
            raise PipelineCancelled("Job cancelled by user")


def _check_dependencies() -> None:
    missing: list[str] = []
    try:
        from shortube.remotion_bridge import RemotionError, _find_npx
        _find_npx()
    except (RemotionError, OSError) as e:
        missing.append(str(e))

    cfg = get_settings()
    remotion_dir = Path(cfg.remotion_project_dir)
    if not remotion_dir.is_absolute():
        remotion_dir = cfg.base_dir / remotion_dir
    pkg_json = remotion_dir / "package.json"
    if not pkg_json.exists():
        missing.append(f"Remotion project not found at {remotion_dir}")
    if missing:
        raise DependencyError(
            f"Missing dependencies: {', '.join(missing)}. "
            "Ensure Node.js is installed and Remotion project is set up."
        )


def _sanitize_filename(text: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*]', "", text.lower().replace(" ", "_"))
    return safe[:60] or "untitled"


def _output_dir(topic: str) -> Path:
    slug = _sanitize_filename(topic)
    return get_settings().base_dir / "output" / slug


class PipelineOrchestrator:
    """Runs one topic end-to-end: script, voiceover, storyboard, assemble, upload.

    Resume: a cached chain (script_json + storyboard_json + voiceover files)
    is reused all-or-nothing so scene timings always match the audio. If any
    piece is missing, everything is regenerated from the script.
    """

    def __init__(self, db: Database | None = None) -> None:
        self._db = db or Database()

    def _resume_chain(
        self, video: VideoRow | None, default_voice: str
    ) -> tuple[bool, Script | None, Storyboard | None, str]:
        if video is None:
            return False, None, None, default_voice
        try:
            cached_script = Script.from_dict(json.loads(video.script_json))
            cached_storyboard = Storyboard.from_dict(
                json.loads(video.storyboard_json)
            )
            cached_voice = video.voiceover_path or ""
            if (
                cached_script.full_text
                and cached_storyboard.scenes
                and cached_voice
                and Path(cached_voice).exists()
            ):
                logger.info("Resuming from cached script + storyboard + voiceover")
                return True, cached_script, cached_storyboard, cached_voice
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            logger.info("Cache incomplete (%s) — regenerating chain", e)
        return False, None, None, default_voice

    def run(
        self,
        topic: str,
        privacy: str = "public",
        channel_id: str | None = None,
        dry_run: bool = False,
        video_id: int | None = None,
        on_progress: Callable[[StageEvent], None] | None = None,
        cancel: CancelToken | None = None,
    ) -> dict[str, str]:
        _check_dependencies()
        cfg = get_settings()
        channel_id = channel_id or cfg.upload_channel_id or None
        db = self._db
        result: dict[str, str] = {}
        out = _output_dir(topic)
        out.mkdir(parents=True, exist_ok=True)

        def _progress(stage: Stage) -> None:
            if cancel is not None and cancel.cancelled():
                if video_id:
                    db.update_video(video_id, status="cancelled")
                raise PipelineCancelled("Job cancelled by user")
            message = STAGE_LABELS[stage]
            logger.info(message)
            if on_progress:
                on_progress(StageEvent(stage=stage))

        resume_ready = False
        script: Script | None = None
        storyboard: Storyboard | None = None
        voice_path = str(out / "voiceover.mp3")
        video = db.get_video(video_id) if video_id else None
        resume_ready, script, storyboard, voice_path = self._resume_chain(
            video, voice_path
        )

        # Stage 1: Script
        if resume_ready:
            result["script"] = "done (cached)"
        else:
            _progress(Stage.SCRIPT)
            script = generate_script(topic)
            if video_id:
                db.update_video(
                    video_id,
                    script_json=json.dumps(script.to_dict()),
                    status="script_done",
                )
            result["script"] = "done"

        # Stage 2: Voiceover
        if resume_ready:
            result["voiceover"] = voice_path
        else:
            _progress(Stage.VOICEOVER)
            # YouTube Shorts cap is 60s total; reserve bumper + transition time.
            max_audio = 60.0 - 2 * cfg.bumper_duration - 1.5
            generate_voiceover(
                script.hook, script.points, script.cta, voice_path,
                max_duration=max_audio,
            )
            if video_id:
                db.update_video(video_id, voiceover_path=voice_path,
                                status="voiceover_done")
            result["voiceover"] = voice_path

        # Stage 3: Storyboard
        if resume_ready:
            result["storyboard"] = "done (cached)"
        else:
            _progress(Stage.STORYBOARD)
            storyboard = generate_storyboard(script, voice_path)
            if video_id:
                db.update_video(
                    video_id,
                    storyboard_json=json.dumps(storyboard.to_dict()),
                    status="storyboard_done",
                )
            result["storyboard"] = "done"

        # Stage 4: Assembly
        video_path = str(out / "final.mp4")
        cached_video_path = video.video_path if video else None
        if (
            resume_ready
            and cached_video_path
            and Path(cached_video_path).exists()
            and video.status in ("assembled", "uploaded")
        ):
            video_path = cached_video_path
            logger.info("Stage 4 already done, skipping")
        else:
            _progress(Stage.ASSEMBLE)
            last_error: Exception | None = None
            for attempt in (1, 2):
                try:
                    assemble_video(storyboard, voice_path, video_path)
                    last_error = None
                    break
                except (AssemblyError, RemotionError, OSError) as e:
                    last_error = e
                    logger.warning(
                        "Assembly attempt %d failed: %s", attempt, e
                    )
                    Path(video_path).unlink(missing_ok=True)
            if last_error is not None:
                raise PipelineError(f"Assembly failed after retry: {last_error}")
            # Sanity-check the produced file (Remotion can exit 0 on no-op)
            produced = Path(video_path)
            if not produced.exists() or produced.stat().st_size < 10_000:
                produced.unlink(missing_ok=True)
                raise PipelineError("Assembly produced no usable output file")
            if video_id:
                db.update_video(video_id, video_path=video_path, status="assembled")
        result["video"] = video_path

        if dry_run:
            logger.info("Dry-run — skipping upload")
            return result

        # Thumbnail
        _progress(Stage.THUMBNAIL)
        thumb_path = str(out / "thumbnail.jpg")
        try:
            generate_thumbnail(script.title, thumb_path, subtitle=script.hook)
            result["thumbnail"] = thumb_path
        except OSError as e:
            logger.warning("Thumbnail failed: %s", e)

        # Upload
        _progress(Stage.UPLOAD)
        url = upload_script(video_path, script, privacy, channel_id)
        result["url"] = url

        if video_id:
            db.update_video(video_id, thumbnail_path=thumb_path,
                            youtube_url=url, status="uploaded")

        logger.info("Pipeline complete — %s", url)
        return result


def run_pipeline(
    topic: str,
    privacy: str = "public",
    channel_id: str | None = None,
    dry_run: bool = False,
    video_id: int | None = None,
    progress_callback: Callable[[StageEvent], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, str]:
    """Convenience wrapper that adapts a threading.Event to a CancelToken."""
    cancel = CancelToken(cancel_event) if cancel_event is not None else None
    return PipelineOrchestrator().run(
        topic,
        privacy=privacy,
        channel_id=channel_id,
        dry_run=dry_run,
        video_id=video_id,
        on_progress=progress_callback,
        cancel=cancel,
    )