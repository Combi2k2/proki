"""ts_min(x, w): the smallest of x's known values in the last w minutes.

    ts_min(focus, 60)                 your lowest focus this hour

Unknown if none is known.
"""

from __future__ import annotations

import operator

from proki.core.ops.base import Operand, TsExtremum
from proki.utils import span


class TsMin(TsExtremum):
    USAGE = "ts_min(x, w)"
    ABOUT = "the smallest value over the last w minutes"
    beats = operator.lt

    def __init__(self, x: Operand, w: float):
        super().__init__(x, span(w))
