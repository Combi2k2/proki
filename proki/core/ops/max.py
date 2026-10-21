"""max(x, y, ...): the largest of the values, each cycle (unknown if any is).
"""

from __future__ import annotations

from proki.core.ops.base import Operand
from proki.core.ops.lift import Lift


class Max(Lift):
    def __init__(self, *xs: Operand):
        super().__init__(max, *xs, type="number")
