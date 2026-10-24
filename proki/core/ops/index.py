"""index(xs, x): the place of x in a list, the first if it's there more than once.

    work.tasks[index(work.tasks.id, item.id)]     the task `item` is, now

Unknown if it isn't there.
"""

from __future__ import annotations

from proki.core.ops.base import Operand
from proki.core.ops.lift import Lift


class Index(Lift):
    USAGE = "index(xs, x)"
    ABOUT = "the place of x in a list: work.tasks[index(work.tasks.id, item.id)]"

    def __init__(self, xs: Operand, x: Operand):
        super().__init__(lambda v, x: v.index(x) if isinstance(v, list | tuple) and x in v else None, xs, x, type="integer")
