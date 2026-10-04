"""Run slow calls (openjev, the AI) off the UI thread and get the result back on it."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable

from PySide6.QtCore import QObject, QTimer

_pool = ThreadPoolExecutor(max_workers=2)


class Background(QObject):
    """`run(fn, then)`: call fn() in a worker thread, then then(result) on the UI thread."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._jobs: list[tuple[Future, Callable]] = []
        self._timer = QTimer(self, interval=100)
        self._timer.timeout.connect(self._check)

    def run(self, fn: Callable[[], object], then: Callable[[object], None]) -> None:
        self._jobs.append((_pool.submit(fn), then))
        self._timer.start()

    def _check(self) -> None:
        for job in [j for j in self._jobs if j[0].done()]:
            self._jobs.remove(job)
            future, then = job
            then(future.result() if future.exception() is None else None)  # failures arrive as None
        if not self._jobs:
            self._timer.stop()
