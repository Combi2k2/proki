"""delay(x, d): x as it was d minutes ago."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.ops.base import Operand, Queued
from proki.utils import minutes


class Delay(Queued):
    """`x` as it was `d` minutes ago: the latest value at or before t − d."""

    def __init__(self, x: Operand, d: float):
        super().__init__(x, minutes(d))

    at: datetime | None = None

    def drop(self, before: datetime) -> None:
        while len(self.queue) > 1 and self.queue[1][0] <= before:  # keep the one holding at t − d
            self.queue.popleft()
        self.at = before

    def compute(self) -> Any:
        if not self.queue or self.at is None or self.queue[0][0] > self.at:
            return None
        return self.queue[0][1]
