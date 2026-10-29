"""ts_corr(x, y, w): how closely x and y move together over the last w minutes, from -1 (one
up as the other's down) through 0 (no link) to 1 (up and down together).

    ts_corr(keys, focus, 60)          whether you type more as you focus, this hour

Only the moments both are known count (True counts as 1). Unknown with fewer than two, or
while either stays the same.
"""

from __future__ import annotations

from datetime import datetime
from math import sqrt
from typing import Any

from proki.core.ops.base import Operand, Queued
from proki.core.ops.lift import Lift
from proki.utils import boolean, numeric, span


class TsCorr(Queued):
    USAGE = "ts_corr(x, y, w)"
    ABOUT = "how closely x and y move together over the last w minutes, from -1 to 1"

    def __init__(self, x: Operand, y: Operand, w: float):
        super().__init__(Paired(x, y), span(w))
        self.n, self.sx, self.sy, self.sxx, self.syy, self.sxy = 0, 0.0, 0.0, 0.0, 0.0, 0.0

    def take(self, t: datetime, v: Any) -> None:
        super().take(t, v)
        self.count(v, 1)

    def pop(self, row: tuple[datetime, Any]) -> None:
        self.count(row[1], -1)
        if self.n == 0:
            self.sx = self.sy = self.sxx = self.syy = self.sxy = 0.0  # no rounding drift

    def count(self, pair: Any, by: int) -> None:
        """A pair of values in (1) or out (-1) of the sums, if both are numbers."""
        if pair is None or not all(numeric(v) or boolean(v) for v in pair):
            return
        a, b = float(pair[0]), float(pair[1])
        self.n   += by
        self.sx  += by * a
        self.sy  += by * b
        self.sxx += by * a * a
        self.syy += by * b * b
        self.sxy += by * a * b

    def compute(self) -> Any:
        if self.n < 2:
            return None
        varx = self.sxx - self.sx * self.sx / self.n
        vary = self.syy - self.sy * self.sy / self.n
        if varx <= 1e-12 or vary <= 1e-12:  # one stays the same: nothing to move with
            return None
        return max(-1.0, min(1.0, (self.sxy - self.sx * self.sy / self.n) / sqrt(varx * vary)))


class Paired(Lift, function=False):
    """x and y's values side by side, each cycle: their past too, at the moments both keep one."""

    def __init__(self, x: Operand, y: Operand):
        super().__init__(lambda a, b: (a, b), x, y, unknown=True, type="any")

    def history(self, since: datetime) -> list[tuple[datetime, Any]]:
        ys = dict(self.inputs[1].history(since))
        return [(t, (v, ys[t])) for t, v in self.inputs[0].history(since) if t in ys]
