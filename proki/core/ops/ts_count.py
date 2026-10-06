"""ts_count(x, w): how many times x changed to a new value in the last w minutes.

    ts_count(app, 2)            app switches in the last 2 minutes
    ts_count(in_session, 60)    sessions started in the last hour (True / False: how many
                                times it became True)

Unknown values are skipped: x before and after a gap is compared directly. The first
value ever seen doesn't count as a change.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.ops.base import Operand, Queued
from proki.utils import minutes, same


class TsCount(Queued):
    """The queue holds (time, whether x changed then). `changes` is how many in the window."""

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
