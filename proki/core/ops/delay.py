"""delay(x, d): x as it was d minutes ago."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.ops.base import Operand, Queued
from proki.utils import minutes


class Delay(Queued):
    """`x` as it was `d` minutes ago: the latest value at or before t - d. Fresh when that
    value is a new one of x's (d after x took it), not when x is: over a slow input the
    two differ."""

    def __init__(self, x: Operand, d: float):
        super().__init__(x, minutes(d))

    at: datetime | None = None
    shown: datetime | None = None  # when x took the value it gives now

    def advance(self, t: datetime) -> None:
        super().advance(t)
        shown = self.queue[0][0] if self.queue and self.at is not None and self.queue[0][0] <= self.at else None
        self.fresh = shown is not None and shown != self.shown
        self.shown = shown

    def drop(self, before: datetime) -> None:
        while len(self.queue) > 1 and self.queue[1][0] <= before:  # keep the one holding at t − d
            self.queue.popleft()
        self.at = before

    def compute(self) -> Any:
        if not self.queue or self.at is None or self.queue[0][0] > self.at:
            return None
        return self.queue[0][1]
