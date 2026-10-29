"""max(x, y, ...): the largest of the values. max(xs): a list's largest known item.

    max(deadline - time, 0)           the minutes left, none if it's past

Unknown if any value is, or if the list has no known item.
"""

from __future__ import annotations

from proki.core.ops.base import Operand, least, listed
from proki.core.ops.lift import Lift


class Max(Lift):
    USAGE = "max(x, y, ...)"
    ABOUT = "the largest of the values, now, or max(xs) of a list's items"

    def __init__(self, *xs: Operand):
        super().__init__(lambda *vs: least(max, *vs), *xs, type=lambda of: listed(self, of))
