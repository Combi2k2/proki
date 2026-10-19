"""clip(x, low, high): x, kept between low and high, each cycle (unknown if any is).
"""

from __future__ import annotations

from proki.core.ops.base import Operand
from proki.core.ops.lift import Lift


class Clip(Lift):
    def __init__(self, x: Operand, low: Operand, high: Operand):
        super().__init__(lambda v, lo, hi: min(max(v, lo), hi), x, low, high)
