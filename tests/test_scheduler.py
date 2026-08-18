"""Scheduler persistence: daily counter survives restarts, updates stick."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


def _load_scheduler(monkeypatch, base_dir: Path):
    """Load a fresh scheduler module bound to the given base_dir."""
    from shortube.config import Settings, reset_settings

    reset_settings()
    orig_init = Settings.__init__

    def patched_init(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        self.base_dir = base_dir

    monkeypatch.setattr(Settings, "__init__", patched_init)
    monkeypatch.setattr("shortube.config.get_settings", lambda: Settings())

    sched = importlib.import_module("shortube.scheduler")
    sched = importlib.reload(sched)
    sched._load_config()
    return sched


@pytest.fixture
def scheduler(tmp_path, monkeypatch):
    sched = _load_scheduler(monkeypatch, tmp_path)
    yield sched
    sched.stop_scheduler()


def test_daily_counter_persists_across_restarts(tmp_path, monkeypatch):
    sched = _load_scheduler(monkeypatch, tmp_path)
    sched._reset_daily_count()
    sched._generated_today = 7
    sched._last_date = "2026-08-15"
    sched._save_config()

    sched = _load_scheduler(monkeypatch, tmp_path)
    assert sched._generated_today == 7
    assert sched._last_date == "2026-08-15"

    sched._last_date = "2000-01-01"
    sched._reset_daily_count()
    assert sched._generated_today == 0
    assert sched._last_date != "2000-01-01"
    assert not (tmp_path / "output" / ".scheduler_config.json").exists()
    sched.stop_scheduler()


def test_update_keeps_counter_and_toggles_scheduler(scheduler):
    scheduler._generated_today = 3
    cfg = scheduler.update_schedule_config({"enabled": False, "interval_hours": 8})
    assert cfg["generated_today"] == 3
    assert cfg["interval_hours"] == 8
    assert cfg["running"] is False


def test_legacy_json_config_migrated_to_db(tmp_path, monkeypatch):
    legacy = tmp_path / "output" / ".scheduler_config.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps({
        "enabled": True,
        "interval_hours": 12,
        "max_daily": 2,
        "niche": "space",
        "generated_today": 3,
        "last_date": "2026-08-16",
    }), encoding="utf-8")

    sched = _load_scheduler(monkeypatch, tmp_path)
    assert sched._schedule_config["interval_hours"] == 12
    assert sched._generated_today == 3
    assert not legacy.exists()
    raw = sched.db.get_kv(sched._KV_KEY)
    assert json.loads(raw)["niche"] == "space"
    sched.stop_scheduler()


def test_db_is_authoritative_after_migration(tmp_path, monkeypatch):
    sched = _load_scheduler(monkeypatch, tmp_path)
    sched.update_schedule_config({"interval_hours": 24, "enabled": False})
    assert sched._schedule_config["interval_hours"] == 24

    reloaded = _load_scheduler(monkeypatch, tmp_path)
    assert reloaded._schedule_config["interval_hours"] == 24
    reloaded.stop_scheduler()