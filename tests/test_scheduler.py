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
    sched._CONFIG_PATH = base_dir / "output" / ".scheduler_config.json"
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
    data = json.loads(
        (tmp_path / "output" / ".scheduler_config.json").read_text(encoding="utf-8")
    )
    assert data["generated_today"] == 0
    sched.stop_scheduler()


def test_update_keeps_counter_and_toggles_scheduler(scheduler):
    scheduler._generated_today = 3
    cfg = scheduler.update_schedule_config({"enabled": False, "interval_hours": 8})
    assert cfg["generated_today"] == 3
    assert cfg["interval_hours"] == 8
    assert cfg["running"] is False
