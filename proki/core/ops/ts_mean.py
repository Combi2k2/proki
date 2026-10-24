"""ts_mean(x, w): the average of x's known values in the last w minutes (True counts as 1).

    ts_mean(focus, 5)                 your focus, the last 5 minutes
    ts_mean(session.active, 60)       the share of this hour you were in a session

Unknown if none is known.
"""

from __future__ import annotations

from typing import Any

from proki.core.ops.base import Operand, TsArithmetic
from proki.utils import span


class TsMean(TsArithmetic):
    USAGE = "ts_mean(x, w)"
    ABOUT = "the average of the known values over the last w minutes"

    def __init__(self, x: Operand, w: float):
        super().__init__(x, span(w))

    def compute(self) -> Any:
        return self.total / self.known if self.known else None
