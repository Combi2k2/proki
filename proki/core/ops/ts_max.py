"""ts_max(x, w): the largest of x's known values in the last w minutes.

    ts_max(focus, 60)                 your best focus this hour

Unknown if none is known.
"""

from __future__ import annotations

import operator

from proki.core.ops.base import Operand, TsExtremum
from proki.utils import span


class TsMax(TsExtremum):
    USAGE = "ts_max(x, w)"
    ABOUT = "the largest value over the last w minutes"
    beats = operator.gt

    def __init__(self, x: Operand, w: float):
        super().__init__(x, span(w))
