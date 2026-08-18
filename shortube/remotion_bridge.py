from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path

from shortube.config import get_settings
from shortube.quality import resolve_preset
from shortube.template_loader import load_template
from shortube.types import Storyboard

logger = logging.getLogger(__name__)

_NPX_PATH: str | None = None
_RENDER_LOCK = threading.Lock()


def _db_to_linear_volume(db_value: float) -> float:
    """Map the legacy '20 - db' volume setting to a linear Remotion volume."""
    db = db_value - 20.0
    return max(0.0, min(1.0, 10 ** (db / 20.0)))


def _render_dir(remotion_dir: Path, render_id: str) -> Path:
    return remotion_dir / "public" / "render" / render_id


def _cleanup_public(remotion_dir: Path) -> None:
    render_root = remotion_dir / "public" / "render"
    if render_root.exists():
        shutil.rmtree(render_root, ignore_errors=True)
        logger.debug("Cleaned up Remotion public/render")


def _copy_to_public(src: str, remotion_dir: Path, render_id: str) -> str:
    """Copy a file to Remotion's public dir and return a staticFile()-compatible path."""
    pub_dir = _render_dir(remotion_dir, render_id)
    pub_dir.mkdir(parents=True, exist_ok=True)

    src_path = Path(src)
    if not src_path.exists():
        return ""

    dest = pub_dir / src_path.name
    if not dest.exists():
        shutil.copy2(str(src_path), str(dest))
        logger.debug("Copied %s -> %s", src, dest)

    rel = str(dest.relative_to(remotion_dir / "public")).replace("\\", "/")
    return rel


def _find_npx() -> str:
    global _NPX_PATH
    if _NPX_PATH:
        return _NPX_PATH

    found = shutil.which("npx")
    if found:
        _NPX_PATH = found
        return found

    common_paths = [
        Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "nodejs",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "nodejs",
        Path(os.environ.get("LOCALAPPDATA", "")) / "fnm" / "node-versions",
    ]
    for p in common_paths:
        candidates = [
            p / "npx.cmd",
            p / "npx",
            p / "npx.exe",
        ]
        for c in candidates:
            if c.exists():
                _NPX_PATH = str(c)
                logger.debug("Found npx at %s", _NPX_PATH)
                return _NPX_PATH

    raise RemotionError(
        "npx not found. Ensure Node.js and npm are installed and on PATH."
    )


class RemotionError(Exception):
    pass


def _acquire_render_lock() -> object | None:
    """Serialize renders (in-process threading lock)."""
    _RENDER_LOCK.acquire()
    return _RENDER_LOCK


def _release_render_lock(token: object | None) -> None:
    if token is None:
        return
    if token is _RENDER_LOCK:
        _RENDER_LOCK.release()


def composition_frames(
    scenes: list, fps: int, bumper_frames: int, transition_frames: int
) -> int:
    """Exact frame count of ShortubeVideo for the given scenes.

    Matches ShortubeVideo.tsx: total = 2*bumper + sum(floor(scene.dur*fps))
    + (n-2)*transition_frames (transitions add time, they don't overlap).
    """
    n = len(scenes)
    scene_frames = sum(int(s.duration * fps) for s in scenes)
    return 2 * bumper_frames + scene_frames + max(0, n - 2) * transition_frames


def _prepare_input_json(
    storyboard: Storyboard,
    voiceover_path: str,
    output_path: str,
    word_timestamps: list[dict],
    remotion_dir: Path,
    render_id: str,
) -> str:
    cfg = get_settings()
    scenes_data = []
    for scene in storyboard.scenes:
        media_path = None
        media_type = None
        for asset in scene.selected_media:
            if asset.local_path:
                media_path = _copy_to_public(asset.local_path, remotion_dir, render_id)
                media_type = asset.type
                break
        scenes_data.append({
            "index": scene.index,
            "startTime": scene.start_time,
            "endTime": scene.end_time,
            "duration": scene.duration,
            "narration": scene.narration,
            "imagePath": media_path,
            "mediaType": media_type,
        })

    music_path = ""
    if cfg.background_music_path and Path(cfg.background_music_path).exists():
        music_path = _copy_to_public(cfg.background_music_path, remotion_dir, render_id)

    sfx_paths: dict[str, str] = {}
    if cfg.sfx_enabled:
        sfx_dir = Path(cfg.sfx_dir)
        if not sfx_dir.is_absolute():
            sfx_dir = cfg.base_dir / sfx_dir
        for key, name in (
            ("whoosh", "whoosh.wav"),
            ("pop", "pop.wav"),
            ("riser", "riser.wav"),
        ):
            asset = sfx_dir / name
            if asset.exists():
                sfx_paths[key] = _copy_to_public(str(asset), remotion_dir, render_id)

    voiceover_rel = _copy_to_public(voiceover_path, remotion_dir, render_id)

    input_data = {
        "script": {
            "topic": storyboard.script.topic,
            "hook": storyboard.script.hook,
            "points": storyboard.script.points,
            "cta": storyboard.script.cta,
        },
        "scenes": scenes_data,
        "voiceoverPath": voiceover_rel,
        "musicPath": music_path,
        "timestamps": word_timestamps,
        "bumperDuration": cfg.bumper_duration,
        "transitionDuration": cfg.transition_duration,
        "musicVolume": _db_to_linear_volume(cfg.music_volume),
        "duckThreshold": cfg.duck_threshold,
        "captionFontSize": cfg.caption_font_size,
        "template": cfg.template,
        "templateData": load_template(cfg.template),
        "sfxEnabled": cfg.sfx_enabled,
        "sfxWhooshPath": sfx_paths.get("whoosh", ""),
        "sfxPopPath": sfx_paths.get("pop", ""),
        "sfxRiserPath": sfx_paths.get("riser", ""),
        "videoWidth": cfg.video_width,
        "videoHeight": cfg.video_height,
        "fps": cfg.video_fps,
    }

    input_file = (
        Path(tempfile.gettempdir()) / f"shortube_remotion_input_{render_id}.json"
    )
    input_file.write_text(json.dumps(input_data, indent=2), encoding="utf-8")
    logger.debug("Remotion input written to %s", input_file)
    return str(input_file)


def render_video(
    storyboard: Storyboard,
    voiceover_path: str,
    output_path: str,
    word_timestamps: list[dict],
) -> str:
    cfg = get_settings()
    remotion_dir = Path(cfg.remotion_project_dir)
    if not remotion_dir.is_absolute():
        remotion_dir = cfg.base_dir / remotion_dir
    if not remotion_dir.exists():
        raise RemotionError(f"Remotion project not found: {remotion_dir}")

    lock_token = _acquire_render_lock()
    render_id = uuid.uuid4().hex[:12]
    try:
        _cleanup_public(remotion_dir)
        input_file = _prepare_input_json(
            storyboard, voiceover_path, output_path, word_timestamps,
            remotion_dir, render_id,
        )

        preset = resolve_preset(cfg.quality)
        fps = preset.fps or cfg.video_fps
        bumper_frames = int(cfg.bumper_duration * fps)
        transition_frames = int(cfg.transition_duration * fps)
        total_frames = composition_frames(
            storyboard.scenes, fps, bumper_frames, transition_frames
        )
        if total_frames < 1:
            raise RemotionError("Composition would be empty (no frames)")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        npx_cmd = _find_npx()
        entry_file = remotion_dir / "src" / "index.ts"
        if not entry_file.exists():
            raise RemotionError(f"Entry file not found: {entry_file}")

        cmd = [
            npx_cmd, "remotion", "render",
            str(entry_file.resolve()),
            "ShortubeVideo",
            str(output.resolve()),
            "--props=" + input_file,
            "--frames=" + f"0-{total_frames - 1}",
            f"--width={cfg.video_width}",
            f"--height={cfg.video_height}",
            f"--fps={fps}",
            f"--crf={preset.crf}",
        ]

        concurrency = cfg.remotion_concurrency
        if concurrency <= 0:
            concurrency = preset.concurrency
        if concurrency > 0:
            cmd.append(f"--concurrency={concurrency}")
            logger.info("Using concurrency: %d", concurrency)

        logger.info(
            "Remotion render starting: %d frames (%ds + transitions + bumpers) "
            "quality=%s crf=%d",
            total_frames, storyboard.total_duration, cfg.quality, preset.crf,
        )
        logger.debug("Command: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                cwd=str(remotion_dir.resolve()),
                capture_output=True,
                text=True,
                timeout=3600,
                check=False,
            )
            if result.returncode != 0:
                stderr = result.stderr[-3000:] if result.stderr else ""
                raise RemotionError(
                    f"Remotion render failed (exit {result.returncode}):\n{stderr}"
                )
            logger.info("Remotion render complete: %s", output_path)
        except subprocess.TimeoutExpired:
            raise RemotionError("Remotion render timed out after 1 hour") from None
        except FileNotFoundError:
            raise RemotionError(
                "npx not found. Ensure Node.js and npm are installed and on PATH."
            ) from None
    finally:
        _release_render_lock(lock_token)

    if not output.exists():
        raise RemotionError(f"Remotion did not produce output file: {output_path}")

    return str(output)
