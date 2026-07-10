from __future__ import annotations

import logging
import os
import pickle
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from PIL import Image, ImageDraw, ImageFont

from shortube.config import get_settings
from shortube.types import Script

logger = logging.getLogger(__name__)


class UploadError(Exception):
    pass


# ── YouTube Upload ───────────────────────────────────────────────────

def _get_service():
    cfg = get_settings()
    token_path = cfg.base_dir / "youtube_token.pkl"
    creds = None

    if token_path.exists():
        with open(token_path, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            secrets_path = cfg.youtube_client_secrets
            if not os.path.exists(secrets_path):
                raise UploadError(
                    f"client_secrets.json not found at {secrets_path}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                secrets_path, cfg.youtube_scopes
            )
            creds = flow.run_local_server(port=8080)
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)

    return build("youtube", "v3", credentials=creds)


def list_channels() -> list[dict]:
    try:
        youtube = _get_service()
        response = youtube.channels().list(part="snippet", mine=True).execute()
        return [
            {"id": ch["id"], "title": ch["snippet"]["title"]}
            for ch in response.get("items", [])
        ]
    except HttpError as e:
        logger.error("YouTube API error listing channels: %s", e)
        return []


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: list[str] | None = None,
    privacy: str | None = None,
    channel_id: str | None = None,
    publish_at: str | None = None,
    playlist_id: str | None = None,
) -> str:
    cfg = get_settings()
    youtube = _get_service()
    tags = tags or cfg.tags_default
    privacy = privacy or cfg.upload_privacy

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": cfg.upload_category,
            "defaultLanguage": cfg.upload_language,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    if channel_id:
        body["snippet"]["channelId"] = channel_id
    if publish_at:
        body["status"]["publishAt"] = publish_at
        body["status"]["privacyStatus"] = "private"

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    try:
        response = youtube.videos().insert(
            part="snippet,status", body=body, media_body=media,
        ).execute()
        video_id = response.get("id")
        if not video_id:
            raise UploadError(f"YouTube API returned no video ID: {response}")

        if playlist_id:
            try:
                youtube.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": playlist_id,
                            "resourceId": {
                                "kind": "youtube#video",
                                "videoId": video_id,
                            },
                        }
                    },
                ).execute()
                logger.info("Video added to playlist %s", playlist_id)
            except HttpError as e:
                logger.warning("Failed to add to playlist: %s", e)

        return f"https://youtu.be/{video_id}"
    except HttpError as e:
        raise UploadError(f"YouTube upload failed: {e}")


# ── Thumbnail ────────────────────────────────────────────────────────

class ThumbnailError(Exception):
    pass


def generate_thumbnail(
    title: str,
    output_path: str,
    subtitle: str = "",
) -> str:
    width, height = 1280, 720
    img = Image.new("RGB", (width, height), (10, 10, 10))
    draw = ImageDraw.Draw(img)

    bg_path = Path("assets/thumbnail_bg.png")
    if bg_path.exists():
        try:
            bg = Image.open(bg_path).resize((width, height))
            img.paste(bg, (0, 0))
        except Exception as e:
            logger.warning("Failed to load thumbnail background: %s", e)

    try:
        title_font = ImageFont.truetype(
            "C:/Windows/Fonts/arialbd.ttf", 56
        )
        sub_font = ImageFont.truetype(
            "C:/Windows/Fonts/arial.ttf", 32
        )
    except Exception:
        title_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()

    lines = []
    words = title.split()
    line = ""
    for word in words:
        test = f"{line} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=title_font)
        if bbox[2] - bbox[0] > width - 80:
            lines.append(line)
            line = word
        else:
            line = test
    if line:
        lines.append(line)

    y = height // 2 - (len(lines) * 30)
    for line_text in lines:
        bbox = draw.textbbox((0, 0), line_text, font=title_font)
        tw = bbox[2] - bbox[0]
        x = (width - tw) // 2
        draw.text((x + 2, y + 2), line_text, fill="black", font=title_font)
        draw.text((x, y), line_text, fill="white", font=title_font)
        y += 65

    if subtitle:
        bbox = draw.textbbox((0, 0), subtitle, font=sub_font)
        sw = bbox[2] - bbox[0]
        sx = (width - sw) // 2
        sy = y + 10
        draw.text((sx + 1, sy + 1), subtitle, fill="black", font=sub_font)
        draw.text((sx, sy), subtitle, fill="#cccccc", font=sub_font)

    img.save(output_path, "JPEG", quality=95)
    logger.info("Thumbnail saved to %s", output_path)
    return output_path


# ── Combined ─────────────────────────────────────────────────────────

def upload_script(
    video_path: str,
    script: Script,
    privacy: str = "public",
    channel_id: str | None = None,
) -> str:
    hashtags = " ".join(f"#{t.replace(' ', '')}" for t in script.tags[:8])
    points_bullets = "\n".join(f"\u2022 {p}" for p in script.points)
    description = (
        f"{script.hook}\n\n{points_bullets}\n\n"
        f"{script.cta}\n\n{hashtags}"
    )
    tags = list(script.tags)
    while tags and len(",".join(tags)) > 500:
        tags.pop()

    cfg = get_settings()
    url = upload_video(
        video_path=video_path,
        title=script.title,
        description=description,
        tags=tags,
        privacy=privacy,
        channel_id=channel_id,
        publish_at=cfg.upload_publish_at or None,
        playlist_id=cfg.upload_playlist_id or None,
    )
    return url
