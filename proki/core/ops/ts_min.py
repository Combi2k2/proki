"""ts_min(x, w): the minimum of x's known values over the last w minutes."""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any

from proki.core.ops.base import Operand, Queued
from proki.utils import minutes


class TsMin(Queued):
    """Beside the queue, a monotonic queue of (time, value) that can still be the minimum: a
    newer value drops those it beats, so its front is the window's minimum."""

    def __init__(self, x: Operand, w: float):
        super().__init__(x, minutes(w))
        self.best: deque[tuple[datetime, Any]] = deque()

    def take(self, t: datetime, v: Any) -> None:
        super().take(t, v)
        if v is None:
            return
        while self.best and v < self.best[-1][1]:
            self.best.pop()
        self.best.append((t, v))

    def pop(self, row: tuple[datetime, Any]) -> None:
        while self.best and self.best[0][0] <= row[0]:
            self.best.popleft()

    def compute(self) -> Any:
        return self.best[0][1] if self.best else None
