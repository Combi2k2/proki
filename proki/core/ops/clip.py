"""clip(x, lo, hi): x, kept between lo and hi.

    clip(focus * 2, 0, 1)             twice focus, 1 at most

Unknown if any of them is.
"""

from __future__ import annotations

from proki.core.ops.base import Operand
from proki.core.ops.lift import Lift


class Clip(Lift):
    USAGE = "clip(x, lo, hi)"
    ABOUT = "x, kept between lo and hi"

    def __init__(self, x: Operand, low: Operand, high: Operand):
        super().__init__(lambda v, lo, hi: min(max(v, lo), hi), x, low, high, type="number")
