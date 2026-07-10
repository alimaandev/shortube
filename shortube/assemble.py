from __future__ import annotations

import json
import logging
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pydub import AudioSegment

from shortube.config import get_settings
from shortube.types import Storyboard

logger = logging.getLogger(__name__)

TEMP_DIR = Path(tempfile.gettempdir()) / "shortube_assembly"


def _ensure_temp():
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def _run(cmd: list[str], desc: str = "") -> None:
    logger.info("FFmpeg: %s", desc or " ".join(cmd[:8]))
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode()[:2000] if e.stderr else ""
        raise RuntimeError(f"FFmpeg {desc} failed:\n{stderr}")


def _make_bumper(text: str, duration: float, fade_out: bool) -> Path:
    cfg = get_settings()
    path = TEMP_DIR / f"bumper_{hash(text)}.mp4"
    if path.exists():
        return path

    # Generate frame as image (avoids all FFmpeg drawtext escaping issues)
    img = Image.new("RGB", (cfg.video_width, cfg.video_height), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 56)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (cfg.video_width - tw) // 2
    y = (cfg.video_height - th) // 2
    draw.text((x, y), text, fill="white", font=font)

    frame_path = TEMP_DIR / f"bumper_frame_{hash(text)}.png"
    img.save(frame_path)

    # Encode image to video with fade
    fade_filter = (
        f"fade=out:st={duration - cfg.transition_duration}:d={cfg.transition_duration}"
        if fade_out else
        f"fade=in:st=0:d={cfg.transition_duration}"
    )
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(frame_path),
        "-vf", fade_filter,
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-t", str(duration),
        str(path),
    ]
    _run(cmd, "bumper")
    return path


def _scene_clip(
    media_path: str | None, duration: float, index: int,
) -> Path:
    cfg = get_settings()
    path = TEMP_DIR / f"scene_{index}.mp4"
    if path.exists():
        return path

    if not media_path or not Path(media_path).exists():
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i",
            f"color=c=#141414:s={cfg.video_width}x{cfg.video_height}:"
            f"d={duration}:r={cfg.video_fps}",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            str(path),
        ]
        _run(cmd, f"scene_{index}_fallback")
        return path

    zoom_dur = max(duration - 0.5, 1.0)
    zoompan = (
        f"zoompan=z='if(lte(on,1),1,"
        f"min(1.08,1+0.08*(on/{zoom_dur*cfg.video_fps})))':"
        f"d={int(duration*cfg.video_fps)}:"
        f"s={cfg.video_width}x{cfg.video_height}:fps={cfg.video_fps}"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", media_path,
        "-vf",
        f"scale={cfg.video_width}:{cfg.video_height}:"
        f"force_original_aspect_ratio=increase,"
        f"crop={cfg.video_width}:{cfg.video_height},{zoompan}",
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-t", str(duration),
        str(path),
    ]
    _run(cmd, f"scene_{index}")
    return path


def _concat(clip_paths: list[Path], output: Path) -> None:
    if len(clip_paths) == 1:
        _run(["ffmpeg", "-y", "-i", str(clip_paths[0]),
              "-c", "copy", str(output)], "concat")
        return

    concat_file = TEMP_DIR / "concat.txt"
    with open(concat_file, "w") as f:
        for cp in clip_paths:
            f.write(f"file '{cp.resolve()}'\n")

    _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file), "-c", "copy", str(output),
    ], "concat")


def _add_audio(video: Path, audio: str, output: Path) -> None:
    _run([
        "ffmpeg", "-y", "-i", str(video), "-i", audio,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(output),
    ], "add_audio")


def _add_captions(video: Path, captions: list[dict], output: Path) -> None:
    if not captions:
        _run(["ffmpeg", "-y", "-i", str(video), "-c", "copy",
              str(output)], "no_captions")
        return

    srt_path = TEMP_DIR / "captions.srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, cap in enumerate(captions, 1):
            start = cap.get("start", 0)
            end = cap.get("end", start + 2)
            text = cap.get("word", cap.get("text", ""))
            # Safety net: strip any remaining HTML/SSML tags
            text = re.sub(r"<[^>]+>", "", text).strip()
            if not text:
                continue
            f.write(f"{i}\n")
            f.write(f"{_srt_time(start)} --> {_srt_time(end)}\n")
            f.write(f"{text}\n\n")

    # Escape the drive letter colon so FFmpeg subtitles filter doesn't
    # interpret it as a parameter separator.
    # FFmpeg filter graph uses \\: for a literal colon on Windows paths
    srt_filter = str(srt_path.resolve()).replace("\\", "/").replace(":", "\\\\:")
    vid_str = str(video.resolve()).replace("\\", "/")

    cmd = [
        "ffmpeg", "-y",
        "-i", vid_str,
        "-vf", f"subtitles={srt_filter}",
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(Path(output).resolve()),
    ]
    _run(cmd, "captions")


def _srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _mix_music(voiceover_path: str, output_path: str) -> str:
    cfg = get_settings()
    music = cfg.background_music_path
    if not music or not Path(music).exists():
        return voiceover_path

    try:
        voice = AudioSegment.from_file(voiceover_path)
        bg = AudioSegment.from_file(music)
        bg = bg - (20 - cfg.music_volume)

        if len(bg) < len(voice):
            bg = bg * ((len(voice) // len(bg)) + 1)
        bg = bg[:len(voice)]

        silence = AudioSegment.silent(duration=10)
        voiced = (voice + silence) - cfg.duck_threshold
        voiced = voiced[:len(voice)]

        mixed = bg.overlay(voice + voiced, position=0)
        mixed_path = str(Path(output_path).with_name("voiceover_mixed.mp3"))
        mixed.export(mixed_path, format="mp3", bitrate="192k")
        return mixed_path
    except Exception as e:
        logger.warning("Music mixing failed: %s", e)
        return voiceover_path


def _load_timestamps(timestamp_path: str) -> list[dict]:
    ts_file = Path(timestamp_path)
    if not ts_file.exists():
        return []
    try:
        data = json.loads(ts_file.read_text(encoding="utf-8"))
        return data.get("timestamps", [])
    except Exception:
        return []


class AssemblyError(Exception):
    pass


def assemble_video(
    storyboard: Storyboard,
    voiceover_path: str,
    output_path: str,
) -> str:
    _ensure_temp()
    scenes = storyboard.scenes
    if not scenes:
        raise AssemblyError("Storyboard has no scenes")

    cfg = get_settings()

    # Mix background music
    audio_path = _mix_music(voiceover_path, output_path)

    # Build intro bumper
    intro = _make_bumper(storyboard.script.topic, cfg.bumper_duration, True)

    # Build scene clips
    clips: list[Path] = [intro]
    for scene in scenes:
        media_path = None
        for asset in scene.selected_media:
            if asset.local_path:
                media_path = asset.local_path
                break
        clips.append(_scene_clip(media_path, scene.duration, scene.index))

    # Build outro bumper
    outro = _make_bumper(storyboard.script.cta, cfg.bumper_duration, False)
    clips.append(outro)

    # Concat
    concat_video = TEMP_DIR / "concat_video.mp4"
    _concat(clips, concat_video)

    # Add audio
    with_audio = TEMP_DIR / "with_audio.mp4"
    _add_audio(concat_video, audio_path, with_audio)

    # Add captions
    ts_path = str(Path(voiceover_path).with_suffix(".timestamps.json"))
    word_ts = _load_timestamps(ts_path)
    final = Path(output_path)

    if word_ts:
        _add_captions(with_audio, word_ts, final)
    else:
        caption_list = []
        bumper_dur = cfg.bumper_duration
        for scene in scenes:
            caption_list.append({
                "start": bumper_dur + scene.start_time,
                "end": bumper_dur + scene.end_time,
                "text": scene.narration,
            })
        _add_captions(with_audio, caption_list, final)

    logger.info("Video assembled: %s", output_path)
    return output_path
