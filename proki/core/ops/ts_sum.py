"""ts_sum(x, w): x added up over time, in the last w minutes.

Each value counts for the time it covers, in minutes:
    ts_sum(keys, 10)            key presses in the last 10 minutes (keys is per minute)
    ts_sum(in_session, 60)      minutes in a session in the last hour (True counts as 1)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.ops.base import Operand, Queued
from proki.utils import minutes
from proki.core.signals.stream import Stream


class TsSum(Queued):
    """Keeps a running total of the known values. The result multiplies it by the minutes
    each value covers (a cycle, or the input's period for a slow input)."""

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
        return self.total * (self.inputs[0].period or Stream.cycle).total_seconds() / 60  # each value spans its period
