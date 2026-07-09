import logging
import os
import pickle
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

from shortube.config import (
    YOUTUBE_CLIENT_SECRETS,
    YOUTUBE_SCOPES,
    UPLOAD_PRIVACY,
    UPLOAD_CATEGORY,
    UPLOAD_LANGUAGE,
    TAGS_DEFAULT,
    BASE_DIR,
)

TOKEN_PATH = BASE_DIR / "youtube_token.pkl"


def _get_authenticated_service():
    creds = None
    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(YOUTUBE_CLIENT_SECRETS):
                raise FileNotFoundError(
                    f"client_secrets.json not found at {YOUTUBE_CLIENT_SECRETS}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                YOUTUBE_CLIENT_SECRETS, YOUTUBE_SCOPES
            )
            creds = flow.run_local_server(port=8080)
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)

    return build("youtube", "v3", credentials=creds)


def list_channels() -> list[dict]:
    try:
        youtube = _get_authenticated_service()
        request = youtube.channels().list(part="snippet", mine=True)
        response = request.execute()
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
    youtube = _get_authenticated_service()
    tags = tags or TAGS_DEFAULT
    privacy = privacy or UPLOAD_PRIVACY

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": UPLOAD_CATEGORY,
            "defaultLanguage": UPLOAD_LANGUAGE,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    if channel_id:
        body["snippet"]["channelId"] = channel_id
    if publish_at and privacy == "private":
        body["status"]["publishAt"] = publish_at
        if "privacyStatus" in body["status"]:
            body["status"]["privacyStatus"] = "private"

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    try:
        response = request.execute()
        video_id = response.get("id")
        if not video_id:
            raise RuntimeError(f"YouTube API returned no video ID: {response}")

        if playlist_id and video_id:
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
                logger.info("Added video %s to playlist %s", video_id, playlist_id)
            except HttpError as e:
                logger.warning("Failed to add to playlist: %s", e)

        return f"https://youtu.be/{video_id}"
    except HttpError as e:
        raise RuntimeError(f"YouTube upload failed: {e}")