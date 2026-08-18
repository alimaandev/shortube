from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from shortube.db import Database
from shortube.pipeline import (
    DependencyError,
    PipelineCancelled,
    PipelineError,
    StageEvent,
    run_pipeline,
)

logger = logging.getLogger(__name__)


class _JobRunner(QObject):
    started = pyqtSignal(int, str)
    progress = pyqtSignal(int, str, int)
    finished = pyqtSignal(int, dict)
    failed = pyqtSignal(int, str)
    cancelled = pyqtSignal(int)

    def __init__(self, job_queue: queue.Queue) -> None:
        super().__init__()
        self._queue = job_queue

    @pyqtSlot()
    def run(self) -> None:
        db = Database()
        while True:
            spec = self._queue.get()
            if spec is None:
                return
            job_id = spec["job_id"]
            video_id = spec["video_id"]
            topic = spec["topic"]
            cancel_event = spec["cancel_event"]

            def callback(ev: StageEvent, job_id: int = job_id) -> None:
                self.progress.emit(job_id, ev.message, ev.percent)

            db.update_job(job_id, status="running")
            self.started.emit(job_id, topic)
            try:
                result = run_pipeline(
                    topic,
                    privacy=spec["privacy"],
                    channel_id=spec.get("channel_id"),
                    video_id=video_id,
                    progress_callback=callback,
                    cancel_event=cancel_event,
                )
                if "url" in result:
                    db.mark_topic_used(topic)
                db.update_job(job_id, status="done", progress=100)
                self.finished.emit(job_id, result)
            except PipelineCancelled:
                db.update_job(job_id, status="cancelled", error="Cancelled by user")
                self.cancelled.emit(job_id)
            except (DependencyError, PipelineError) as e:
                db.update_job(job_id, status="failed", error=str(e), progress=0)
                self.failed.emit(job_id, str(e))
            except Exception as e:
                logger.exception("Job %d failed unexpectedly", job_id)
                db.update_job(job_id, status="failed", error=str(e), progress=0)
                self.failed.emit(job_id, str(e))


class JobManager(QObject):
    jobQueued = pyqtSignal(int, str)
    jobStarted = pyqtSignal(int, str)
    jobProgress = pyqtSignal(int, str, int)
    jobFinished = pyqtSignal(int, dict)
    jobFailed = pyqtSignal(int, str)
    jobCancelled = pyqtSignal(int)
    queueLengthChanged = pyqtSignal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._queue: queue.Queue = queue.Queue()
        self._current: dict[str, Any] | None = None
        self._cancel_event = threading.Event()

        self._thread = QThread(self)
        self._thread.setObjectName("job-runner")
        self._runner = _JobRunner(self._queue)
        self._runner.moveToThread(self._thread)
        self._thread.started.connect(self._runner.run)

        self._runner.started.connect(self.jobStarted)
        self._runner.progress.connect(self.jobProgress)
        self._runner.finished.connect(self._on_finished)
        self._runner.failed.connect(self._on_failed)
        self._runner.cancelled.connect(self._on_cancelled)

        self._thread.start()

    def _on_finished(self, job_id: int, result: dict) -> None:
        self._current = None
        self._cancel_event.clear()
        self.jobFinished.emit(job_id, result)

    def _on_failed(self, job_id: int, error: str) -> None:
        self._current = None
        self._cancel_event.clear()
        self.jobFailed.emit(job_id, error)

    def _on_cancelled(self, job_id: int) -> None:
        self._current = None
        self._cancel_event.clear()
        self.jobCancelled.emit(job_id)

    def submit(
        self,
        job_id: int,
        video_id: int,
        topic: str,
        privacy: str = "private",
        channel_id: str | None = None,
    ) -> None:
        spec = {
            "job_id": job_id,
            "video_id": video_id,
            "topic": topic,
            "privacy": privacy,
            "channel_id": channel_id,
            "cancel_event": self._cancel_event,
        }
        self._current = spec
        self._queue.put(spec)
        self.jobQueued.emit(job_id, topic)
        self.queueLengthChanged.emit(self._queue.qsize())

    def cancel_current(self) -> None:
        if self._current is not None:
            self._cancel_event.set()

    @property
    def is_busy(self) -> bool:
        return self._current is not None and not self._cancel_event.is_set()

    def shutdown(self) -> None:
        if self._thread.isRunning():
            self._queue.put(None)
            self._thread.quit()
            self._thread.wait(5000)


_ACTIVE_THREADS: list[QThread] = []


def run_in_thread(
    fn: Callable[[], Any],
    on_done: Callable[[Any], None],
    on_error: Callable[[str], None] | None = None,
) -> None:
    """Run a short blocking function in a helper thread (discovery, tests, ...)."""

    class _Worker(QObject):
        done = pyqtSignal(object)
        error = pyqtSignal(str)

        @pyqtSlot()
        def run(self) -> None:
            try:
                self.done.emit(fn())
            except Exception as e:  # noqa: BLE001 — thread boundary: any failure must surface via error signal
                logger.error("Background task failed: %s", e)
                self.error.emit(str(e))

    worker = _Worker()
    thread = QThread()
    _ACTIVE_THREADS.append(thread)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.done.connect(on_done)
    if on_error is not None:
        worker.error.connect(on_error)
    worker.done.connect(thread.quit)
    worker.error.connect(thread.quit)
    worker.done.connect(worker.deleteLater)
    worker.error.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.finished.connect(lambda: _prune_threads())
    thread.start()


def _prune_threads() -> None:
    for t in [t for t in _ACTIVE_THREADS if not t.isRunning()]:
        if t in _ACTIVE_THREADS:
            _ACTIVE_THREADS.remove(t)
