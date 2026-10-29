"""ts_sum(x, w): x added up over the last w minutes, each value for the minutes it covers.

    ts_sum(keys, 10)                  key presses in the last 10 minutes (keys is per minute)
    ts_sum(active, 60)                minutes on the computer in the last hour (True counts as 1)

0 if none is known.
"""

from __future__ import annotations

from typing import Any

from proki.core.ops.base import Operand, TsArithmetic
from proki.core.signals.stream import Stream
from proki.utils import span


class TsSum(TsArithmetic):
    USAGE = "ts_sum(x, w)"
    ABOUT = "the total over the last w minutes: a rate gives a count, true / false gives minutes"

    def __init__(self, x: Operand, w: float):
        super().__init__(x, span(w))

    def compute(self) -> Any:
        return self.total * (self.inputs[0].period or Stream.cycle).total_seconds() / 60  # each value for the minutes it covers
