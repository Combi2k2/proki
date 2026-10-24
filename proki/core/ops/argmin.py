"""argmin(xs): the place of a list's smallest known item, the first of equals.

    tasks[argmin(tasks.deadline)]     the task due first

Unknown if it has no known item.
"""

from __future__ import annotations

from proki.core.ops.base import Operand, place
from proki.core.ops.lift import Lift


class Argmin(Lift):
    USAGE = "argmin(xs)"
    ABOUT = "the place of a list's smallest item: tasks[argmin(tasks.deadline)], the one due first"

    def __init__(self, xs: Operand):
        super().__init__(lambda v: place(min, v), xs, type="integer")
