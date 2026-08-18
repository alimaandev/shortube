# Contributing to Shortube

Thanks for wanting to contribute! This guide covers how to set up your
environment, the workflow we use, and the quality gates every change must
pass before it lands on `master`.

## Table of Contents

- [Development Setup](#development-setup)
- [Project Layout](#project-layout)
- [Workflow](#workflow)
- [Quality Gates](#quality-gates)
- [Testing](#testing)
- [Code Style](#code-style)
- [Reporting Bugs & Ideas](#reporting-bugs--ideas)

## Development Setup

Prerequisites: Python 3.11+, Node.js 18+, and (recommended) ffmpeg on PATH.

```bash
# Python dependencies
pip install -r requirements.txt

# Remotion renderer
cd remotion
npm install
cd ..
```

Run the desktop app:

```bash
python -m shortube.desktop
```

Run the CLI:

```bash
python -m shortube.main generate -t "Mind-blowing facts about the universe"
```

### Environment

The app reads configuration from `.env` in the project root. Copy the
reference keys from the README's [Configuration Reference](./README.md#️-configuration-reference).
No key is required to boot — the setup wizard in the app will walk you through it.

## Project Layout

```
shortube/
├── desktop/          # PyQt6 app (thin views over the core)
├── pipeline.py       # PipelineOrchestrator: typed stages + resume
├── script.py         # ScriptWriter: LLM script generation + validation
├── llm.py            # One OpenAI-compatible LLM client
├── db.py             # SQLite (versioned migrations, typed rows)
├── discover.py       # Trend discovery engine
├── upload.py         # YouTube Data API v3
└── ...               # see README Architecture section
tests/                # pytest suite (mirrors shortube/ structure)
remotion/             # TypeScript renderer
templates/            # Visual templates (JSON)
```

## Workflow

1. **Create a branch** off `master` — `git checkout -b <your-feature>`.
   Use a descriptive name, e.g. `fix/thumbnail-crash`, `feat/podcast-mode`.
2. **Make your change** — small, focused commits with clear messages.
3. **Run the quality gates** (below) — they must all pass locally.
4. **Push and open a PR** — the CI pipeline runs the same gates
   (lint + unit tests on every PR; the real-render E2E smoke test on
   `master` pushes).
5. **Wait for review** — a maintainer will review and merge.

We work with small, focused PRs. If a change is bigger than a few hundred
lines, consider splitting it.

## Quality Gates

Every change must pass all of these:

| Gate | Command | Notes |
|------|---------|-------|
| Lint | `python -m ruff check shortube tests` | zero warnings |
| Unit tests | `python -m pytest` | E2E render auto-skips without `SHORTUBE_E2E` |
| Byte-compile | `python -m compileall -q shortube` | import-time syntax check |
| Renderer types | `npx tsc --noEmit` (in `remotion/`) | |
| App boot | offscreen `MainWindow()` construction | see below |
| E2E render | `SHORTUBE_E2E=1 python -m pytest -m e2e` | real Remotion render |

Boot check (PowerShell / Linux):

```bash
QT_QPA_PLATFORM=offscreen python -c "from PyQt6.QtWidgets import QApplication; from shortube.desktop.main_window import MainWindow; app = QApplication([]); w = MainWindow(); w.close(); app.quit()"
```

## Testing

- New behavior ships with tests. Place them in `tests/` mirroring the
  module structure (`test_pipeline.py` tests `shortube/pipeline.py`).
- Unit tests never touch the network or real LLM/YouTube APIs — use
  `monkeypatch` like the existing suites do.
- The `settings` fixture in `tests/conftest.py` isolates `.env`/DB/output
  into a temp dir; use it whenever a test touches configuration or storage.
- The E2E render test (`-m e2e`) is gated behind `SHORTUBE_E2E=1` because
  it renders real video. It needs Node.js and `remotion/node_modules`.

## Code Style

- `ruff` with the project config in `pyproject.toml` — run
  `python -m ruff check shortube tests` before committing.
- Type hints everywhere; `from __future__ import annotations`.
- No comments unless they explain *why*, not *what*.
- Blind `except Exception` is only allowed at genuine boundaries
  (thread/CLI/scheduler), and must carry a `# noqa: BLE001` with the reason.

## Reporting Bugs & Ideas

- Use the GitHub issue templates — they make sure we get the info we need.
- Bugs: include the full error/traceback, OS/Python versions, and steps to reproduce.
- Ideas: describe the problem you're solving, not just the feature name.
- For security issues, use [SECURITY.md](./SECURITY.md) — do not open a public issue.
