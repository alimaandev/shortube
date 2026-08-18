"""Shared fixtures for the Shortube test suite."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Qt must see the offscreen platform before PyQt6 is imported anywhere.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def settings(tmp_path, monkeypatch):
    """Settings whose base_dir is isolated in a temp dir.

    Every module reads settings through shortube.config.get_settings(),
    so swapping that one function redirects all .env/db/output access
    into the per-test temp directory.
    """
    from shortube.config import Settings, reset_settings

    reset_settings()
    orig_init = Settings.__init__

    def patched_init(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        self.base_dir = tmp_path

    monkeypatch.setattr(Settings, "__init__", patched_init)
    monkeypatch.setattr("shortube.config.get_settings", lambda: Settings())
    yield Settings()
    reset_settings()


@pytest.fixture(scope="session")
def qapp():
    """Session-wide QApplication (offscreen) for Qt-based tests."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    return app
