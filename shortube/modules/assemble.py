from __future__ import annotations

import json
import logging
from pathlib import Path

from moviepy import (
    AudioFileClip,
    ColorClip,
    CompositeAudioClip,
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
    vfx,
)
from pydub import AudioSegment

logger = logging.getLogger(__name__)

from shortube.config import (
    BUMPER_DURATION,
    CAPTION_FONT,
    CAPTION_FONT_COLOR,
    CAPTION_FONT_SIZE,
    CAPTION_STROKE_COLOR,
    CAPTION_STROKE_WIDTH,
    TRANSITION_DURATION,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
)
from shortube.config.settings import get_settings
from shortube.core.types import MediaType, Scene, Storyboard


# ── Helpers ────────────────────────────────────────────────────────────


def _make_bumper(text: str, color: tuple = (0, 0, 0)) -> ColorClip:
    clip = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=color)
    txt = TextClip(
        text=text,
        font_size=56,
        color="white",
        font=CAPTION_FONT,
        size=(int(VIDEO_WIDTH * 0.8), None),
        method="caption",
        text_align="center",
    ).with_position("center")
    return CompositeVideoClip([clip, txt], size=(VIDEO_WIDTH, VIDEO_HEIGHT)).with_duration(
        BUMPER_DURATION
    )


def _make_text_clip(text: str, duration: float) -> TextClip:
    return TextClip(
        text=text,
        font_size=CAPTION_FONT_SIZE,
        color=CAPTION_FONT_COLOR,
        stroke_color=CAPTION_STROKE_COLOR,
        stroke_width=CAPTION_STROKE_WIDTH,
        font=CAPTION_FONT,
        size=(int(VIDEO_WIDTH * 0.9), None),
        method="caption",
        text_align="center",
    ).with_duration(duration).with_position(("center", "center"))


def _make_text_clip_animated(text: str, duration: float) -> TextClip:
    clip = _make_text_clip(text, duration)
    fade = min(0.3, duration * 0.2)
    return clip.with_effects([vfx.FadeIn(fade)])


def _load_media_asset(media_path: str, target_size: tuple[int, int]) -> VideoFileClip | ColorClip:
    path = Path(media_path)
    if not path.exists() or path.stat().st_size == 0:
        fallback = ColorClip(size=target_size, color=(20, 20, 20))
        return fallback.with_duration(1.0)
    try:
        clip = VideoFileClip(str(path)).resized(target_size)
        return clip
    except Exception as e:
        logger.warning("Failed to load video %s: %s", media_path, e)
        fallback = ColorClip(size=target_size, color=(20, 20, 20))
        return fallback.with_duration(1.0)


def _ken_burns_effect(clip: VideoFileClip | ColorClip) -> VideoFileClip | ColorClip:
    if not hasattr(clip, "duration") or clip.duration is None:
        return clip
    dur = clip.duration
    if dur < 1.5:
        return clip
    try:
        zoom_in = 1.0
        zoom_out = 1.08
        clip = clip.with_effects([
            vfx.Resize(lambda t: zoom_in + (zoom_out - zoom_in) * (t / dur))
        ])
        if hasattr(clip, "duration") and clip.duration:
            clip = clip.with_position(lambda t: (
                -10 * (t / dur),
                -10 * (t / dur),
            ))
        return clip
    except Exception:
        return clip


def _load_sfx(path: str) -> AudioFileClip | None:
    if not path or not Path(path).exists():
        return None
    try:
        return AudioFileClip(path)
    except Exception as e:
        logger.warning("Failed to load SFX %s: %s", path, e)
        return None


def _mix_sound_effects(
    video: VideoFileClip,
    output_path: str,
    transition_times: list[float],
) -> VideoFileClip:
    sfx_dir = Path("assets/sfx")
    if not sfx_dir.exists():
        return video

    sfx_clips: list[AudioFileClip] = []
    for t in transition_times:
        for name in ("whoosh.mp3", "transition.mp3", "swish.mp3"):
            path = str(sfx_dir / name)
            sfx = _load_sfx(path)
            if sfx:
                sfx = sfx.with_start(max(0, t))
                sfx = sfx.with_duration(min(sfx.duration, 1.0))
                sfx_clips.append(sfx)
                break

    if not sfx_clips:
        return video

    try:
        existing = video.audio
        all_audio = [existing] + sfx_clips if existing else sfx_clips
        new_audio = CompositeAudioClip(all_audio)
        return video.with_audio(new_audio)
    except Exception as e:
        logger.warning("SFX mixing failed: %s", e)
        return video


def _mix_background_music(voiceover_path: str, output_path: str, music_path: str | None = None) -> str:
    """Mix voiceover with background music using audio ducking."""
    settings = get_settings()
    music = music_path or settings.background_music_path
    if not music or not Path(music).exists():
        logger.info("No background music found — using voiceover only")
        return voiceover_path

    try:
        voice = AudioSegment.from_file(voiceover_path)
        bg = AudioSegment.from_file(music)

        music_volume = settings.music_volume
        duck_threshold = settings.duck_threshold

        bg = bg - (20 - music_volume)

        if len(bg) < len(voice):
            repeats = (len(voice) // len(bg)) + 1
            bg = bg * repeats
        bg = bg[:len(voice)]

        silence = AudioSegment.silent(duration=10)
        voiced_frames = voice + silence
        voiced_frames = voiced_frames - duck_threshold
        voiced_frames = voiced_frames[:len(voice)]

        mixed = bg.overlay(voice + voiced_frames, position=0)

        mixed_path = str(Path(output_path).with_name("voiceover_mixed.mp3"))
        mixed.export(mixed_path, format="mp3", bitrate="192k")
        logger.info("Mixed background music into %s", mixed_path)
        return mixed_path
    except Exception as e:
        logger.warning("Audio mixing failed: %s — using voiceover only", e)
        return voiceover_path


def _load_word_timestamps(timestamp_path: str) -> list[dict]:
    """Load word-level timestamps from a .timestamps.json file."""
    ts_file = Path(timestamp_path)
    if not ts_file.exists():
        return []
    try:
        data = json.loads(ts_file.read_text(encoding="utf-8"))
        return data.get("timestamps", [])
    except Exception:
        return []


# ── Legacy pipeline (unchanged) ───────────────────────────────────────

def _load_audio_safe(path: str) -> AudioFileClip:
    if not Path(path).exists() or Path(path).stat().st_size == 0:
        raise RuntimeError(f"Voiceover file missing or empty: {path}")
    try:
        return AudioFileClip(path)
    except Exception as e:
        raise RuntimeError(f"Failed to load voiceover {path}: {e}")


def assemble(
    video_paths: list[str],
    voiceover_path: str,
    script_data: dict,
    output_path: str,
    intro_text: str | None = None,
    outro_text: str | None = None,
) -> str:
    audio = _load_audio_safe(voiceover_path)
    total_duration = audio.duration

    if not video_paths:
        raise RuntimeError("No video clips available to assemble")

    seg_duration = total_duration / len(video_paths)

    clips = []
    for vp in video_paths:
        try:
            clip = VideoFileClip(vp).resized((VIDEO_WIDTH, VIDEO_HEIGHT))
        except Exception as e:
            logger.warning("Skipping corrupt video %s: %s", vp, e)
            continue
        clip = clip.subclipped(0, min(clip.duration, seg_duration + TRANSITION_DURATION))
        clip = clip.with_duration(seg_duration)
        clip = clip.with_effects([vfx.FadeIn(TRANSITION_DURATION), vfx.FadeOut(TRANSITION_DURATION)])
        clips.append(clip)

    for i in range(len(clips) - 1):
        clips[i] = clips[i].with_effects([vfx.CrossFadeOut(TRANSITION_DURATION)])
        clips[i + 1] = clips[i + 1].with_start(clips[i].end - TRANSITION_DURATION)

    video = concatenate_videoclips(clips, method="compose")
    video = video.with_duration(total_duration)
    video = video.with_audio(audio)

    intro = _make_bumper(intro_text or script_data.get("topic", "")).with_effects(
        [vfx.FadeOut(TRANSITION_DURATION)]
    )
    intro_end = intro.duration
    outro = _make_bumper(outro_text or script_data["cta"]).with_effects(
        [vfx.FadeIn(TRANSITION_DURATION)]
    )

    video = video.with_start(intro_end - TRANSITION_DURATION)
    full_duration = intro_end + total_duration + outro.duration - TRANSITION_DURATION

    overlay_texts = []
    hook_start = intro_end - TRANSITION_DURATION
    hook_t = min(5.0, total_duration * 0.2)
    overlay_texts.append(_make_text_clip(script_data["hook"], hook_t).with_start(hook_start))

    segment_len = (total_duration - hook_t) / len(script_data["points"])
    for i, point in enumerate(script_data["points"]):
        t_start = hook_start + hook_t + i * segment_len
        dur = min(segment_len, full_duration - t_start)
        overlay_texts.append(_make_text_clip(point, dur).with_start(t_start))

    final_clips = [intro, video, outro] + overlay_texts
    final = CompositeVideoClip(final_clips, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
    final = final.with_duration(full_duration)
    final.write_videofile(output_path, fps=VIDEO_FPS, codec="libx264", audio_codec="aac")
    return output_path


def _make_word_synced_captions(
    timestamps: list[dict],
    scenes_abs_start: float,
) -> list[TextClip]:
    clips: list[TextClip] = []
    for ts in timestamps:
        dur = ts["end"] - ts["start"]
        if dur <= 0 or not ts.get("word"):
            continue
        clip = TextClip(
            text=ts["word"],
            font_size=CAPTION_FONT_SIZE,
            color=CAPTION_FONT_COLOR,
            stroke_color=CAPTION_STROKE_COLOR,
            stroke_width=CAPTION_STROKE_WIDTH,
            font=CAPTION_FONT,
            size=(int(VIDEO_WIDTH * 0.9), None),
            method="caption",
            text_align="center",
        ).with_duration(dur).with_start(scenes_abs_start + ts["start"]).with_position(("center", "center"))
        clips.append(clip)
    return clips


def _make_word_synced_overlay(
    timestamps: list[dict],
    scenes_abs_start: float,
) -> list[TextClip]:
    if not timestamps:
        return []
    if len(timestamps) <= 2:
        return []
    return _make_word_synced_captions(timestamps, scenes_abs_start)


# ── Storyboard-aware assembly ─────────────────────────────────────────

def _apply_transition(
    clip: VideoFileClip | ColorClip,
    transition: str,
    duration: float,
) -> VideoFileClip | ColorClip:
    if transition == "fade":
        return clip.with_effects([vfx.FadeIn(duration), vfx.FadeOut(duration)])
    if transition == "crossfade":
        return clip.with_effects([vfx.FadeIn(duration)])
    return clip


def assemble_from_storyboard(
    storyboard: Storyboard,
    voiceover_path: str,
    output_path: str,
) -> str:
    audio = _load_audio_safe(voiceover_path)
    total_duration = audio.duration

    scenes = storyboard.scenes
    if not scenes:
        raise RuntimeError("Storyboard has no scenes")

    # ── Build video segments from scenes ──────────────────────────
    video_segments: list[VideoFileClip | ColorClip] = []
    for scene in scenes:
        seg_duration = scene.duration
        if seg_duration <= 0:
            continue

        # Pick the first available media for this scene
        media_clip: VideoFileClip | ColorClip | None = None
        for asset in scene.selected_media:
            if asset.local_path:
                clip = _load_media_asset(asset.local_path, (VIDEO_WIDTH, VIDEO_HEIGHT))
                media_clip = clip
                break

        if media_clip is None:
            media_clip = ColorClip(
                size=(VIDEO_WIDTH, VIDEO_HEIGHT),
                color=(20, 20, 20),
            ).with_duration(seg_duration)
            media_clip = media_clip.with_effects([vfx.FadeIn(TRANSITION_DURATION)])
        else:
            media_clip = media_clip.subclipped(
                0, min(media_clip.duration, seg_duration + TRANSITION_DURATION)
            )
            media_clip = _ken_burns_effect(media_clip)
            media_clip = media_clip.with_duration(seg_duration)
            media_clip = _apply_transition(media_clip, scene.transition, TRANSITION_DURATION)

        video_segments.append(media_clip)

    # ── Crossfade between segments ────────────────────────────────
    for i in range(len(video_segments) - 1):
        seg = video_segments[i]
        if hasattr(seg, "with_effects"):
            video_segments[i] = seg.with_effects([vfx.CrossFadeOut(TRANSITION_DURATION)])
        next_start = video_segments[i].end - TRANSITION_DURATION
        video_segments[i + 1] = video_segments[i + 1].with_start(
            max(next_start, 0)
        )

    video = concatenate_videoclips(video_segments, method="compose")
    video = video.with_duration(total_duration)

    # ── Mix background music ────────────────────────────────────────
    settings = get_settings()
    voiceover_path_for_mix = voiceover_path
    if settings.background_music_path:
        mixed_voice = _mix_background_music(voiceover_path, output_path)
        if mixed_voice != voiceover_path:
            voiceover_path_for_mix = mixed_voice

    audio = _load_audio_safe(voiceover_path_for_mix)
    video = video.with_audio(audio)

    # ── Sound effects on transitions ──────────────────────────────
    transition_times = [0.0]
    for scene in scenes:
        transition_times.append(transition_times[-1] + scene.duration)
    video = _mix_sound_effects(video, output_path, transition_times[1:])

    # ── Intro / Outro bumpers ─────────────────────────────────────

    video = video.with_start(intro_end - TRANSITION_DURATION)
    full_duration = intro_end + total_duration + outro.duration - TRANSITION_DURATION

    # ── Word-synced captions from timestamps ──────────────────────
    scenes_abs_start = intro_end - TRANSITION_DURATION
    ts_path = str(Path(voiceover_path).with_suffix(".timestamps.json"))
    word_ts = _load_word_timestamps(ts_path)

    if word_ts:
        overlay_texts = _make_word_synced_overlay(word_ts, scenes_abs_start)
    else:
        overlay_texts: list[TextClip] = []
        for scene in scenes:
            if not scene.narration:
                continue
            t_start = scenes_abs_start + scene.start_time
            dur = min(scene.duration, full_duration - t_start)
            if dur <= 0:
                continue
            overlay_texts.append(
                _make_text_clip_animated(scene.narration, dur).with_start(t_start)
            )

    final_clips = [intro, video, outro] + overlay_texts
    final = CompositeVideoClip(final_clips, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
    final = final.with_duration(full_duration)
    final.write_videofile(output_path, fps=VIDEO_FPS, codec="libx264", audio_codec="aac")
    return output_path
