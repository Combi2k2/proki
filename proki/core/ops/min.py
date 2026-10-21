"""min(x, y, ...): the smallest of the values, each cycle (unknown if any is).
"""

from __future__ import annotations

from proki.core.ops.base import Operand
from proki.core.ops.lift import Lift


class Min(Lift):
    def __init__(self, *xs: Operand):
        super().__init__(min, *xs, type="number")
