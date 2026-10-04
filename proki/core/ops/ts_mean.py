"""ts_mean(x, w): the mean of x's known values over the last w minutes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.ops.base import Operand, Queued
from proki.utils import minutes


class TsMean(Queued):
    """Running totals of the window's known values and of how many there are."""

    def __init__(self, x: Operand, w: float):
        super().__init__(x, minutes(w))
        self.total, self.known = 0.0, 0

    def take(self, t: datetime, v: Any) -> None:
        super().take(t, v)
        if v is not None:
            self.total += float(v)
            self.known += 1

    def pop(self, row: tuple[datetime, Any]) -> None:
        if row[1] is not None:
            self.total -= float(row[1])
            self.known -= 1
            if self.known == 0:
                self.total = 0.0  # no rounding drift

    def compute(self) -> Any:
        return self.total / self.known if self.known else None
