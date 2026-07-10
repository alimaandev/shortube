from __future__ import annotations

import json
import logging
from pathlib import Path

from shortube.config import get_settings
from shortube.db import Database
from shortube.script import ScriptError, generate_script
from shortube.voice import VoiceError, generate_voiceover
from shortube.storyboard import StoryboardError, generate_storyboard
from shortube.assemble import AssemblyError, assemble_video
from shortube.upload import UploadError, generate_thumbnail, upload_script
from shortube.types import Script

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    pass


def _output_dir(topic: str) -> Path:
    slug = topic.lower().replace(" ", "_")[:40]
    return get_settings().base_dir / "output" / slug


def run_pipeline(
    topic: str,
    privacy: str = "public",
    channel_id: str | None = None,
    dry_run: bool = False,
    video_id: int | None = None,
) -> dict[str, str]:
    cfg = get_settings()
    channel_id = channel_id or cfg.upload_channel_id or None
    db = Database()
    result: dict[str, str] = {}
    out = _output_dir(topic)
    out.mkdir(parents=True, exist_ok=True)

    # Stage 1: Script
    if video_id:
        video = db.get_video(video_id)
        if video and video["status"] in ("script_done", "voiceover_done",
                                          "storyboard_done", "assembled",
                                          "uploaded"):
            logger.info("Stage 1 already done, loading cached script")
            script = Script.from_dict(json.loads(video["script_json"]))
        else:
            script = generate_script(topic)
            db.update_video(video_id, script_json=json.dumps(script.to_dict()),
                            status="script_done")
    else:
        script = generate_script(topic)
    result["script"] = "done"

    # Stage 2: Voiceover
    voice_path = str(out / "voiceover.mp3")
    # Always regenerate to pick up script text fixes (HTML stripping, etc.)
    # Delete cached files first
    for f in [Path(voice_path), Path(voice_path).with_suffix(".timestamps.json")]:
        if f.exists():
            f.unlink()
    generate_voiceover(script.hook, script.points, script.cta, voice_path)
    if video_id:
        db.update_video(video_id, voiceover_path=voice_path,
                        status="voiceover_done")
    result["voiceover"] = voice_path

    # Stage 3: Storyboard
    if video_id:
        video = db.get_video(video_id)
        if video and video["status"] in ("storyboard_done", "assembled",
                                          "uploaded"):
            logger.info("Stage 3 already done, skipping")
        else:
            storyboard = generate_storyboard(script, voice_path)
            db.update_video(video_id, status="storyboard_done")
    else:
        storyboard = generate_storyboard(script, voice_path)
    result["storyboard"] = "done"

    # Stage 4: Assembly
    video_path = str(out / "final.mp4")
    if video_id:
        video = db.get_video(video_id)
        if video and video["status"] in ("assembled", "uploaded"):
            logger.info("Stage 4 already done, skipping")
            video_path = video["video_path"] or video_path
        else:
            assemble_video(storyboard, voice_path, video_path)
            db.update_video(video_id, video_path=video_path, status="assembled")
    else:
        assemble_video(storyboard, voice_path, video_path)
    result["video"] = video_path

    if dry_run:
        logger.info("Dry-run — skipping upload")
        return result

    # Thumbnail
    thumb_path = str(out / "thumbnail.jpg")
    try:
        generate_thumbnail(script.title, thumb_path, subtitle=script.hook)
        result["thumbnail"] = thumb_path
    except Exception as e:
        logger.warning("Thumbnail failed: %s", e)

    # Upload
    logger.info("Uploading to YouTube...")
    url = upload_script(video_path, script, privacy, channel_id)
    result["url"] = url

    if video_id:
        db.update_video(video_id, thumbnail_path=thumb_path,
                        youtube_url=url, status="uploaded")

    logger.info("Pipeline complete — %s", url)
    return result
