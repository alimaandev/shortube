from __future__ import annotations

import logging
import sys


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    _configure_logging()

    from PyQt6.QtWidgets import QApplication, QMessageBox

    from shortube.desktop.main_window import MainWindow
    from shortube.desktop.setup_wizard import SetupWizard, needs_setup
    from shortube.desktop.theme import build_stylesheet

    app = QApplication(sys.argv)
    app.setApplicationName("Shortube Studio")
    app.setOrganizationName("Shortube")
    app.setStyleSheet(build_stylesheet())

    window = MainWindow()
    window.show()

    if needs_setup():
        wizard = SetupWizard(window)
        wizard.exec()

    missing = _missing_dependencies()
    if missing:
        QMessageBox.warning(
            window,
            "Missing dependencies",
            "Some features may not work:\n\n" + "\n".join(f"• {m}" for m in missing),
        )

    return app.exec()


def _missing_dependencies() -> list[str]:
    missing: list[str] = []
    try:
        from shortube.remotion_bridge import RemotionError, _find_npx

        _find_npx()
    except (RemotionError, OSError) as e:
        missing.append(str(e))
    from pathlib import Path

    from shortube.config import get_settings

    cfg = get_settings()
    remotion_dir = Path(cfg.remotion_project_dir)
    if not remotion_dir.is_absolute():
        remotion_dir = cfg.base_dir / remotion_dir
    if not (remotion_dir / "package.json").exists():
        missing.append(
            f"Remotion project not found at {remotion_dir} — "
            "run `npm install` inside remotion/ first"
        )
    if _find_ffmpeg() is None:
        missing.append(
            "ffmpeg not found on PATH — loudness normalization will be skipped"
        )
    return missing


def _find_ffmpeg() -> str | None:
    import shutil

    return shutil.which("ffmpeg")
