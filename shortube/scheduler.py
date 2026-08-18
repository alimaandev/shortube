"""Automatic topic discovery + pipeline runner on a schedule.

The schedule configuration (interval, daily cap, niche, privacy and the
daily counter) is persisted in the shared SQLite database (kv table).
Databases from older builds that still carry `output/.scheduler_config.json`
are migrated on first load and the file is removed.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from shortube.config import get_settings
from shortube.db import Database
from shortube.discover import discover
from shortube.pipeline import PipelineError, run_pipeline

logger = logging.getLogger(__name__)

_KV_KEY = "scheduler_config"

_scheduler: BackgroundScheduler | None = None
db = Database()

_schedule_config: dict[str, Any] = {
    "enabled": False,
    "interval_hours": 6,
    "max_daily": 4,
    "niche": "",
    "privacy": "public",
    "generated_today": 0,
    "last_date": "",
}
_generated_today: int = 0
_last_date: str = ""


def _legacy_config_path() -> Path:
    return get_settings().base_dir / "output" / ".scheduler_config.json"


def _migrate_legacy_file() -> None:
    """One-time import of the pre-SQLite scheduler config, then delete it."""
    global _generated_today, _last_date
    legacy = _legacy_config_path()
    if not legacy.exists():
        return
    try:
        data = json.loads(legacy.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            _schedule_config.update(data)
            _generated_today = int(_schedule_config.get("generated_today", 0))
            _last_date = str(_schedule_config.get("last_date", ""))
            _save_config()
            logger.info("Migrated scheduler config from %s", legacy)
    except (json.JSONDecodeError, OSError):
        logger.warning("Ignoring unreadable legacy scheduler config %s", legacy)
    legacy.unlink(missing_ok=True)


def _load_config():
    global _schedule_config, _generated_today, _last_date
    _migrate_legacy_file()
    raw = db.get_kv(_KV_KEY)
    if raw:
        try:
            _schedule_config.update(json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            logger.warning("Ignoring corrupt scheduler config in database")
    # Restore the daily counter so restarts cannot bypass max_daily.
    _generated_today = int(_schedule_config.get("generated_today", 0))
    _last_date = str(_schedule_config.get("last_date", ""))


def _save_config():
    global _generated_today, _last_date
    _schedule_config["generated_today"] = _generated_today
    _schedule_config["last_date"] = _last_date
    db.set_kv(_KV_KEY, json.dumps(_schedule_config))


def _reset_daily_count():
    global _generated_today, _last_date
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    if _last_date != today:
        _generated_today = 0
        _last_date = today
        _save_config()


def _run_scheduled_job():
    global _generated_today
    _reset_daily_count()

    cfg = get_settings()
    niche_val = _schedule_config.get("niche") or cfg.niche
    max_daily = _schedule_config.get("max_daily", 4)
    privacy = _schedule_config.get("privacy", "public")

    if _generated_today >= max_daily:
        logger.info("Daily limit reached (%d/%d)", _generated_today, max_daily)
        return

    try:
        ideas = discover(niche_val, max_results=5)
        for idea in ideas:
            if not db.is_topic_used(idea.title):
                tid = db.add_topic(idea.title, niche=niche_val, source=idea.source, score=idea.score)
                vid = db.create_video(tid, privacy=privacy)
                logger.info("Scheduled: generating '%s' (video #%d)", idea.title[:50], vid)

                def progress(msg: str):
                    logger.debug("Scheduled job: %s", msg)

                result = run_pipeline(
                    idea.title,
                    privacy=privacy,
                    video_id=vid,
                    progress_callback=progress,
                )

                if "url" in result:
                    db.mark_topic_used(idea.title)
                    _generated_today += 1
                    _save_config()
                    logger.info("Scheduled upload complete: %s", result["url"])

                if _generated_today >= max_daily:
                    logger.info("Daily limit reached after this upload")
                return

        logger.info("No undiscovered topics found for scheduled run")
    except PipelineError as e:
        logger.error("Scheduled pipeline failed: %s", e)
    except Exception as e:  # noqa: BLE001 — APScheduler job boundary: an uncaught job error kills the scheduler loop
        logger.error("Scheduled job error: %s", e)


def _get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        _scheduler = BackgroundScheduler(daemon=True)
    return _scheduler


def start_scheduler():
    sched = _get_scheduler()
    if sched.running:
        return

    interval = _schedule_config.get("interval_hours", 6)
    sched.add_job(
        _run_scheduled_job,
        trigger=IntervalTrigger(hours=interval),
        id="auto_generate",
        replace_existing=True,
    )
    sched.start()
    logger.info("Scheduler started (every %dh)", interval)


def stop_scheduler():
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")


def get_schedule_config() -> dict[str, Any]:
    return {
        **_schedule_config,
        "generated_today": _generated_today,
        "running": _scheduler is not None and _scheduler.running,
    }


def update_schedule_config(config: dict[str, Any]) -> dict[str, Any]:
    global _generated_today

    if "enabled" in config:
        _schedule_config["enabled"] = bool(config["enabled"])
    if "interval_hours" in config:
        _schedule_config["interval_hours"] = max(1, int(config["interval_hours"]))
    if "max_daily" in config:
        _schedule_config["max_daily"] = max(1, int(config["max_daily"]))
    if "niche" in config:
        _schedule_config["niche"] = str(config["niche"])
    if "privacy" in config:
        _schedule_config["privacy"] = str(config["privacy"])
    if "generated_today" in config:
        _generated_today = int(config["generated_today"])

    _save_config()

    if _schedule_config.get("enabled"):
        sched = _get_scheduler()
        if sched.running:
            sched.reschedule_job(
                "auto_generate",
                trigger=IntervalTrigger(hours=_schedule_config["interval_hours"]),
            )
        else:
            start_scheduler()
    else:
        if _scheduler is not None and _scheduler.running:
            stop_scheduler()

    return get_schedule_config()


# Load persisted config on module import
_load_config()
