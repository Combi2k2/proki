"""ts_count(x, w): how many times x changed to a new value over the last w minutes
(true / false: how many times it became true). An unknown value (None) is skipped: x
before and after it are compared; the first value known isn't a change."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.ops.base import Operand, Queued
from proki.utils import minutes, same


class TsCount(Queued):
    """The queue holds (time, whether x changed to a new value: not unknown, not false)."""

    def __init__(self, x: Operand, w: float):
        super().__init__(x, minutes(w))
        self.changes, self.last = 0, None

    def take(self, t: datetime, v: Any) -> None:
        changed = v is not None and v is not False and self.last is not None and not same(v, self.last)
        if v is not None:
            self.last = v
        super().take(t, changed)
        self.changes += changed

    def pop(self, row: tuple[datetime, Any]) -> None:
        self.changes -= row[1]

    def compute(self) -> Any:
        return self.changes
