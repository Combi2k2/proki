"""ts_sum(x, w): ∫ x dt over the last w minutes: a rate per minute gives a count, true /
false gives minutes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.ops.base import Operand, Queued
from proki.core.signals import Stream
from proki.utils import minutes


class TsSum(Queued):
    """A running total of the window's known values, each counted over its input's period."""

    def __init__(self, x: Operand, w: float):
        super().__init__(x, minutes(w))
        self.total = 0.0

    def take(self, t: datetime, v: Any) -> None:
        super().take(t, v)
        if v is not None:
            self.total += float(v)

    def pop(self, row: tuple[datetime, Any]) -> None:
        if row[1] is not None:
            self.total -= float(row[1])

    def compute(self) -> Any:
        return self.total * (self.inputs[0].period or Stream.cycle).total_seconds() / 60  # each value spans its period
