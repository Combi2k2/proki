"""ts_rank(x, w): where x's current value stands among the last w minutes' values, in [0, 1]."""

from __future__ import annotations

from typing import Any

from proki.core.ops.base import Operand, Queued
from proki.utils import minutes


class TsRank(Queued):
    """Where the current value stands among the window's known values, in [0, 1]: the
    share below it (ties count half). None with fewer than two."""

    def __init__(self, x: Operand, w: float):
        super().__init__(x, minutes(w))

    def compute(self) -> Any:
        now = self.inputs[0].current()
        known = [v for _, v in self.queue if v is not None]
        if now is None or len(known) < 2:
            return None
        below = sum(1 for v in known if v < now)
        equal = sum(1 for v in known if v == now) - 1  # not itself
        return (below + equal / 2) / (len(known) - 1)
