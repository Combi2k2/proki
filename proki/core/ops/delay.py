"""delay(x, d): x as it was d minutes ago.

    focus - delay(focus, 2)           how much focus changed in the last 2 minutes

Unknown for the first d minutes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.ops.base import Operand, Queued
from proki.utils import span


class Delay(Queued):
    USAGE = "delay(x, d)"
    ABOUT = "x as it was d minutes ago"

    def __init__(self, x: Operand, d: float):
        super().__init__(x, span(d))
        self._typed, self._infer = None, lambda of: of(self.inputs[0])  # its input's
        self.at   : datetime | None = None   # t − d
        self.shown: datetime | None = None   # when x took the value it gives now

    def advance(self, t: datetime) -> None:
        super().advance(t)
        shown = self.queue[0][0] if self.queue and self.at is not None and self.queue[0][0] <= self.at else None
        self.fresh = shown is not None and shown != self.shown  # as the value it gives changes, d minutes after x's did
        self.shown = shown

    def drop(self, before: datetime) -> None:
        while len(self.queue) > 1 and self.queue[1][0] <= before:  # the one holding at t − d stays
            self.queue.popleft()
        self.at = before

    def compute(self) -> Any:
        if not self.queue or self.at is None or self.queue[0][0] > self.at:
            return None
        return self.queue[0][1]
