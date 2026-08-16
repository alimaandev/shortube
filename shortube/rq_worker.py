from __future__ import annotations

import logging
import os

import redis
from rq import Queue, Worker

from shortube.config import get_settings
from shortube.db import Database
from shortube.pipeline import DependencyError, PipelineError, run_pipeline

logger = logging.getLogger(__name__)

db = Database()


def run_pipeline_job(
    topic: str, privacy: str, video_id: int, job_id: int | None = None,
) -> dict:
    def progress(msg: str):
        logger.info("[job:%d] %s", video_id, msg)
        if job_id:
            try:
                job = db.get_job(job_id)
                if job:
                    db.update_job(
                        job_id, progress=min(99, (job.get("progress") or 0) + 1)
                    )
            except Exception:
                pass

    try:
        if job_id:
            db.update_job(job_id, status="running")
        result = run_pipeline(
            topic,
            privacy=privacy,
            video_id=video_id,
            progress_callback=progress,
        )
        if "url" in result:
            db.mark_topic_used(topic)
        db.update_video(video_id, status="uploaded")
        if job_id:
            db.update_job(job_id, status="done", progress=100)
        return result
    except (DependencyError, PipelineError) as e:
        db.update_video(video_id, status="failed", error=str(e))
        if job_id:
            db.update_job(job_id, status="failed", error=str(e))
        raise
    except Exception as e:
        db.update_video(video_id, status="failed", error=str(e))
        if job_id:
            db.update_job(job_id, status="failed", error=str(e))
        raise


def main():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    conn = redis.from_url(redis_url)

    queue = Queue("shortube", connection=conn)
    worker = Worker([queue], connection=conn)
    worker.work()


if __name__ == "__main__":
    main()
