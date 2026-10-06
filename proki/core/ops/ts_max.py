"""ts_max(x, w): the largest of x's known values in the last w minutes.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any

from proki.core.ops.base import Operand, Queued
from proki.utils import minutes


class TsMax(Queued):
    """Keeps a second queue of only the values that can still become the maximum: a new
    value removes the ones it beats, so the front is always the window's maximum, without
    scanning the window."""

    def __init__(self, x: Operand, w: float):
        super().__init__(x, minutes(w))
        self.best: deque[tuple[datetime, Any]] = deque()

    def take(self, t: datetime, v: Any) -> None:
        super().take(t, v)
        if v is None:
            return
        while self.best and v > self.best[-1][1]:
            self.best.pop()
        self.best.append((t, v))

    def pop(self, row: tuple[datetime, Any]) -> None:
        while self.best and self.best[0][0] <= row[0]:
            self.best.popleft()

    def compute(self) -> Any:
        return self.best[0][1] if self.best else None
