"""min(x, y, ...): the smallest of the values. min(xs): a list's smallest known item.

    min(work.tasks.deadline)          the nearest deadline

Unknown if any value is, or if the list has no known item.
"""

from __future__ import annotations

from proki.core.ops.base import Operand, least, listed
from proki.core.ops.lift import Lift


class Min(Lift):
    USAGE = "min(x, y, ...)"
    ABOUT = "the smallest of the values, now, or min(xs) of a list's items"

    def __init__(self, *xs: Operand):
        super().__init__(lambda *vs: least(min, *vs), *xs, type=lambda of: listed(self, of))
