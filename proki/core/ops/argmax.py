"""argmax(xs): the place of a list's largest known item, the first of equals.

    groups[argmax(groups.score)]      the group that scores highest

Unknown if it has no known item.
"""

from __future__ import annotations

from proki.core.ops.base import Operand, place
from proki.core.ops.lift import Lift


class Argmax(Lift):
    USAGE = "argmax(xs)"
    ABOUT = "the place of a list's largest item"

    def __init__(self, xs: Operand):
        super().__init__(lambda v: place(max, v), xs, type="integer")
