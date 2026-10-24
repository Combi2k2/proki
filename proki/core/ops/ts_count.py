"""ts_count(x, w): how many times x changed to a new value in the last w minutes (True /
False: how many times it became True).

    ts_count(app, 2)                  app switches in the last 2 minutes
    ts_count(recorded, 60)            how often this app came on, in the last hour

An unknown stretch is skipped: x before and after it is compared. The first value ever seen
isn't a change.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.ops.base import Operand, Queued
from proki.utils import same, span


class TsCount(Queued):
    USAGE = "ts_count(x, w)"
    ABOUT = "how many times x changed over the last w minutes (true / false: became true)"

    def __init__(self, x: Operand, w: float):
        super().__init__(x, span(w))
        self.changes, self.last = 0, None  # the window holds whether x changed then

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
