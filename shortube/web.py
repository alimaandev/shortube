from __future__ import annotations

import asyncio
import json
import logging
import secrets
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from shortube.config import get_settings
from shortube.db import Database
from shortube.discover import discover
from shortube.pipeline import DependencyError, PipelineError, run_pipeline
from shortube.scheduler import get_schedule_config, update_schedule_config, start_scheduler
from shortube.analytics import refresh_all_analytics

logger = logging.getLogger(__name__)

db = Database()

_running_jobs: dict[int, dict[str, Any]] = {}
_ws_connections: dict[int, set[WebSocket]] = {}
_main_loop: asyncio.AbstractEventLoop | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _main_loop
    _main_loop = asyncio.get_running_loop()
    logger.info("Shortube web server starting")
    if not get_settings().web_token:
        logger.warning(
            "WEB_TOKEN is not set — API authentication is DISABLED. "
            "Set it in .env to protect the API."
        )
    if get_schedule_config().get("enabled"):
        start_scheduler()
        logger.info("Scheduler auto-started")
    yield
    logger.info("Shortube web server shutting down")


app = FastAPI(title="Shortube", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


# ── Auth ──────────────────────────────────────────────────────────────


def _require_auth(
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None),
):
    """Bearer token / X-API-Key gate for mutating endpoints.

    Disabled when WEB_TOKEN is empty (local/LAN tool), logged at startup.
    """
    token = get_settings().web_token
    if not token:
        return None
    provided = ""
    if authorization and authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    elif x_api_key:
        provided = x_api_key.strip()
    if not provided or not secrets.compare_digest(provided, token):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized — missing or invalid API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return None


def _ws_token_ok(websocket: WebSocket) -> bool:
    token = get_settings().web_token
    if not token:
        return True
    provided = websocket.query_params.get("token", "")
    return bool(provided) and secrets.compare_digest(provided, token)


# ── WebSocket ──────────────────────────────────────────────────────────


@app.websocket("/api/ws/job/{job_id}")
async def job_websocket(websocket: WebSocket, job_id: int):
    await websocket.accept()
    if not _ws_token_ok(websocket):
        await websocket.close(code=1008, reason="Unauthorized")
        return
    if job_id not in _ws_connections:
        _ws_connections[job_id] = set()
    _ws_connections[job_id].add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _ws_connections[job_id].discard(websocket)
        if not _ws_connections[job_id]:
            _ws_connections.pop(job_id, None)


def _broadcast_job(job_id: int, data: dict):
    if job_id not in _ws_connections:
        return
    msg = json.dumps(data)
    dead: set[WebSocket] = set()
    for ws in list(_ws_connections.get(job_id, set())):
        if not _send_ws(ws, msg):
            dead.add(ws)
    _ws_connections[job_id] -= dead
    if not _ws_connections[job_id]:
        _ws_connections.pop(job_id, None)


def _send_ws(ws: WebSocket, msg: str) -> bool:
    try:
        coro = ws.send_text(msg)
        if _main_loop is not None:
            fut = asyncio.run_coroutine_threadsafe(coro, _main_loop)
            fut.result(timeout=3)
        else:
            asyncio.run(coro)
        return True
    except Exception:
        return False


# ── API Routes ─────────────────────────────────────────────────────────


@app.get("/api/trends")
def api_trends(niche: str | None = None, count: int = 10):
    cfg = get_settings()
    niche_val = niche or cfg.niche
    try:
        ideas = discover(niche_val, max_results=count)
        results = []
        for idea in ideas:
            tid = db.add_topic(idea.title, niche=niche_val, source=idea.source, score=idea.score)
            results.append({
                "id": tid,
                "title": idea.title,
                "source": idea.source,
                "score": idea.score,
                "url": idea.url,
            })
        return {"trends": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/topics")
def api_topics(limit: int = 100):
    topics = db.get_all_topics(limit=limit)
    return {"topics": topics}


@app.post("/api/generate", dependencies=[Depends(_require_auth)])
def api_generate(payload: dict):
    topic = payload.get("topic", "").strip()
    privacy = payload.get("privacy", "private")
    niche = payload.get("niche", "")

    if not topic:
        raise HTTPException(status_code=400, detail="Topic is required")

    cfg = get_settings()
    niche_val = niche or cfg.niche

    tid = db.add_topic(topic, niche=niche_val)
    vid = db.create_video(tid, privacy=privacy)
    jid = db.create_job(vid, "generate")

    job_info = {
        "job_id": jid,
        "video_id": vid,
        "topic": topic,
        "status": "queued",
        "progress": 0,
    }
    _running_jobs[jid] = job_info

    if cfg.use_rq:
        import redis as redis_lib
        from rq import Queue
        from shortube.rq_worker import run_pipeline_job
        conn = redis_lib.from_url(cfg.redis_url)
        q = Queue("shortube", connection=conn)
        q.enqueue(run_pipeline_job, topic, privacy, vid, jid)
        logger.info("Enqueued job %d via RQ", jid)
    else:
        thread = threading.Thread(
            target=_run_job_worker,
            args=(jid, vid, topic, privacy),
            daemon=True,
        )
        thread.start()

    return job_info


@app.post("/api/auto", dependencies=[Depends(_require_auth)])
def api_auto(payload: dict):
    niche = payload.get("niche", "")
    privacy = payload.get("privacy", "private")

    cfg = get_settings()
    niche_val = niche or cfg.niche

    ideas = discover(niche_val, max_results=5)
    for idea in ideas:
        if not db.is_topic_used(idea.title):
            tid = db.add_topic(idea.title, niche=niche_val, source=idea.source, score=idea.score)
            vid = db.create_video(tid, privacy=privacy)
            jid = db.create_job(vid, "auto")

            job_info = {
                "job_id": jid,
                "video_id": vid,
                "topic": idea.title,
                "status": "queued",
                "progress": 0,
            }
            _running_jobs[jid] = job_info

            if cfg.use_rq:
                import redis as redis_lib
                from rq import Queue
                from shortube.rq_worker import run_pipeline_job
                conn = redis_lib.from_url(cfg.redis_url)
                q = Queue("shortube", connection=conn)
                q.enqueue(run_pipeline_job, idea.title, privacy, vid, jid)
            else:
                thread = threading.Thread(
                    target=_run_job_worker,
                    args=(jid, vid, idea.title, privacy),
                    daemon=True,
                )
                thread.start()

            return job_info

    raise HTTPException(status_code=404, detail="No undiscovered topics found")


@app.post("/api/retry/{video_id}", dependencies=[Depends(_require_auth)])
def api_retry(video_id: int):
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    topic = video.get("topic_title", "").strip()
    privacy = video.get("privacy", "private")
    if not topic:
        raise HTTPException(status_code=400, detail="Video has no topic")

    db.update_video(video_id, status="pending", error="")
    jid = db.create_job(video_id, "retry")

    job_info = {
        "job_id": jid,
        "video_id": video_id,
        "topic": topic,
        "status": "queued",
        "progress": 0,
    }
    _running_jobs[jid] = job_info

    cfg = get_settings()
    channel_id = cfg.upload_channel_id or None
    if cfg.use_rq:
        import redis as redis_lib
        from rq import Queue
        from shortube.rq_worker import run_pipeline_job
        conn = redis_lib.from_url(cfg.redis_url)
        q = Queue("shortube", connection=conn)
        q.enqueue(run_pipeline_job, topic, privacy, video_id, jid)
    else:
        thread = threading.Thread(
            target=_run_job_worker,
            args=(jid, video_id, topic, privacy, channel_id),
            daemon=True,
        )
        thread.start()

    return job_info


@app.get("/api/jobs/{job_id}")
def api_job_status(job_id: int):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": job}


@app.get("/api/jobs")
def api_jobs(limit: int = 50):
    jobs = db.get_all_jobs(limit=limit)
    return {"jobs": jobs}


@app.get("/api/videos")
def api_videos(limit: int = 50):
    videos = db.get_recent_videos(limit=limit)
    return {"videos": videos}


@app.get("/api/videos/{video_id}")
def api_video(video_id: int):
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"video": video}


@app.get("/api/videos/{video_id}/file")
def api_video_file(video_id: int):
    video = db.get_video(video_id)
    if not video or not video.get("video_path"):
        raise HTTPException(status_code=404, detail="Video file not found")
    video_path = video["video_path"]
    if not Path(video_path).exists():
        raise HTTPException(status_code=404, detail="Video file not found on disk")
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=Path(video_path).name,
    )


@app.get("/api/settings")
def api_get_settings():
    cfg = get_settings()
    return {
        "settings": {
            "niche": cfg.niche,
            "voice_name": cfg.voice_name,
            "voice_speed": cfg.voice_speed,
            "voice_volume": cfg.voice_volume,
            "video_width": cfg.video_width,
            "video_height": cfg.video_height,
            "video_fps": cfg.video_fps,
            "bumper_duration": cfg.bumper_duration,
            "transition_duration": cfg.transition_duration,
            "template": cfg.template,
            "background_music_path": cfg.background_music_path,
            "music_volume": cfg.music_volume,
            "duck_threshold": cfg.duck_threshold,
            "sfx_enabled": cfg.sfx_enabled,
            "sfx_dir": cfg.sfx_dir,
            "caption_font_size": cfg.caption_font_size,
            "upload_privacy": cfg.upload_privacy,
            "upload_category": cfg.upload_category,
            "upload_language": cfg.upload_language,
            "upload_channel_id": cfg.upload_channel_id,
            "upload_publish_at": cfg.upload_publish_at,
            "upload_playlist_id": cfg.upload_playlist_id,
            "llm_provider": cfg.llm_provider,
            "llm_model": cfg.llm_model,
            "discovery_model": cfg.discovery_model or cfg.llm_model,
            "llm_temperature": cfg.llm_temperature,
            "tags_default": cfg.tags_default,
            "image_provider": cfg.image_provider,
            "image_provider_fallback": cfg.image_provider_fallback,
            "media_prefer_videos": cfg.media_prefer_videos,
            "use_rq": cfg.use_rq,
            "redis_url": cfg.redis_url,
            "web_token_set": bool(cfg.web_token),
        }
    }


@app.put("/api/settings", dependencies=[Depends(_require_auth)])
def api_update_settings(payload: dict):
    env_path = get_settings().base_dir / ".env"
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    key_map = {
        "niche": "NICHE",
        "voice_name": "VOICE_NAME",
        "voice_speed": "VOICE_SPEED",
        "voice_volume": "VOICE_VOLUME",
        "video_width": "VIDEO_WIDTH",
        "video_height": "VIDEO_HEIGHT",
        "video_fps": "VIDEO_FPS",
        "bumper_duration": "BUMPER_DURATION",
        "transition_duration": "TRANSITION_DURATION",
        "template": "TEMPLATE",
        "background_music_path": "BACKGROUND_MUSIC_PATH",
        "music_volume": "MUSIC_VOLUME",
        "duck_threshold": "DUCK_THRESHOLD",
        "sfx_enabled": "SFX_ENABLED",
        "sfx_dir": "SFX_DIR",
        "caption_font_size": "CAPTION_FONT_SIZE",
        "upload_privacy": "UPLOAD_PRIVACY",
        "upload_category": "UPLOAD_CATEGORY",
        "upload_language": "UPLOAD_LANGUAGE",
        "upload_channel_id": "UPLOAD_CHANNEL_ID",
        "upload_publish_at": "UPLOAD_PUBLISH_AT",
        "upload_playlist_id": "UPLOAD_PLAYLIST_ID",
        "llm_provider": "LLM_PROVIDER",
        "llm_model": "LLM_MODEL",
        "discovery_model": "DISCOVERY_MODEL",
        "llm_temperature": "LLM_TEMPERATURE",
        "tags_default": "TAGS_DEFAULT",
        "image_provider": "IMAGE_PROVIDER",
        "image_provider_fallback": "IMAGE_PROVIDER_FALLBACK",
        "media_prefer_videos": "MEDIA_PREFER_VIDEOS",
        "use_rq": "USE_RQ",
        "redis_url": "REDIS_URL",
        "web_token": "WEB_TOKEN",
    }

    keys_to_remove = set(key_map.values())
    lines = [l for l in lines if not any(l.startswith(k + "=") for k in keys_to_remove)]

    new_lines: list[str] = []
    for py_key, env_key in key_map.items():
        if py_key in payload:
            val = payload[py_key]
            if isinstance(val, bool):
                val = str(val).lower()
            elif isinstance(val, list):
                val = ",".join(val)
            new_lines.append(f"{env_key}={val}")

    lines.extend(new_lines)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Reload settings so changes apply without a restart
    from shortube.config import reset_settings
    reset_settings()

    return {"status": "saved"}


@app.get("/api/channels")
def api_channels():
    from shortube.upload import list_channels
    channels = list_channels()
    return {"channels": channels}


@app.get("/api/schedule")
def api_get_schedule():
    return {"schedule": get_schedule_config()}


@app.put("/api/schedule", dependencies=[Depends(_require_auth)])
def api_update_schedule(payload: dict):
    result = update_schedule_config(payload)
    return {"schedule": result}


@app.get("/api/templates")
def api_templates():
    cfg = get_settings()
    templates_dir = cfg.base_dir / "templates"
    seen = set()
    items = []
    if templates_dir.exists():
        for f in sorted(templates_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            tid = str(data.get("id", f.stem))
            items.append({"id": tid, "name": str(data.get("name", f.stem))})
            seen.add(tid)
    from shortube.template_loader import DEFAULTS
    if DEFAULTS.get("id") not in seen:
        items.append({"id": DEFAULTS["id"], "name": DEFAULTS.get("name", DEFAULTS["id"])})
        seen.add(DEFAULTS["id"])
    if not items:
        items = [{"id": "premium", "name": "Premium Bold"}]
    return {"templates": items}


@app.get("/api/analytics")
def api_analytics():
    stats = refresh_all_analytics()
    return {"analytics": stats}


@app.post("/api/analytics/refresh")
def api_analytics_refresh():
    stats = refresh_all_analytics()
    return {"analytics": stats}


# ── Background Job Worker ─────────────────────────────────────────────


def _run_job_worker(
    job_id: int, video_id: int, topic: str, privacy: str,
    channel_id: str | None = None,
):
    STAGES = [
        "Checking dependencies",
        "Generating script",
        "Generating voiceover",
        "Creating storyboard with media",
        "Assembling video",
        "Generating thumbnail",
        "Uploading to YouTube",
    ]

    def progress_callback(msg: str):
        if job_id in _running_jobs:
            _running_jobs[job_id]["progress_msg"] = msg
        _broadcast_job(job_id, {
            "type": "progress",
            "job_id": job_id,
            "progress_msg": msg,
        })

    try:
        _running_jobs[job_id]["status"] = "running"
        db.update_job(job_id, status="running")
        _broadcast_job(job_id, {
            "type": "status",
            "job_id": job_id,
            "status": "running",
            "progress": 10,
            "progress_msg": STAGES[0],
        })

        result = run_pipeline(
            topic,
            privacy=privacy,
            channel_id=channel_id,
            video_id=video_id,
            progress_callback=progress_callback,
        )

        if "url" in result:
            db.mark_topic_used(topic)
            _running_jobs[job_id]["result_url"] = result["url"]

        db.update_job(job_id, status="done", progress=100)
        _running_jobs[job_id]["status"] = "done"
        _running_jobs[job_id]["progress"] = 100
        _running_jobs[job_id]["result"] = result
        _broadcast_job(job_id, {
            "type": "done",
            "job_id": job_id,
            "status": "done",
            "progress": 100,
            "result": result,
        })

    except DependencyError as e:
        logger.error("Dependency error: %s", e)
        db.update_job(job_id, status="failed", error=str(e), progress=0)
        _running_jobs[job_id]["status"] = "failed"
        _running_jobs[job_id]["error"] = str(e)
        _broadcast_job(job_id, {
            "type": "failed", "job_id": job_id,
            "status": "failed", "error": str(e),
        })
    except PipelineError as e:
        logger.error("Pipeline error: %s", e)
        db.update_job(job_id, status="failed", error=str(e), progress=0)
        _running_jobs[job_id]["status"] = "failed"
        _running_jobs[job_id]["error"] = str(e)
        _broadcast_job(job_id, {
            "type": "failed", "job_id": job_id,
            "status": "failed", "error": str(e),
        })
    except Exception as e:
        logger.error("Job %d failed: %s", job_id, e)
        db.update_job(job_id, status="failed", error=str(e), progress=0)
        _running_jobs[job_id]["status"] = "failed"
        _running_jobs[job_id]["error"] = str(e)
        _broadcast_job(job_id, {
            "type": "failed", "job_id": job_id,
            "status": "failed", "error": str(e),
        })


# ── Static File Serving (React SPA) ───────────────────────────────────


web_build = Path(__file__).resolve().parent.parent / "web" / "dist"
if web_build.exists():
    app.mount("/", StaticFiles(directory=str(web_build), html=True), name="web")
