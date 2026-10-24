"""ts_rank(x, w): where x's value now stands among its values of the last w minutes, from 0
(the lowest) to 1 (the highest), equal ones counting half.

    ts_rank(every(focus, 60), 30 * 1440)    this hour's focus against the month's

Unknown if x is, or with fewer than two known.
"""

from __future__ import annotations

from typing import Any

from proki.core.ops.base import Operand, Queued
from proki.utils import span


class TsRank(Queued):
    USAGE = "ts_rank(x, w)"
    ABOUT = "where x's value stands among the last w minutes' values, from 0 to 1"

    def __init__(self, x: Operand, w: float):
        super().__init__(x, span(w))

    def compute(self) -> Any:
        now   = self.inputs[0].current()
        known = [v for _, v in self.queue if v is not None]
        if now is None or len(known) < 2:
            return None
        below = sum(1 for v in known if v < now)
        equal = sum(1 for v in known if v == now) - 1  # not itself
        return (below + equal / 2) / (len(known) - 1)
