"""len(xs): how many items a list has.

    len(where(work.tasks, work.tasks.ready))      how many tasks can be worked on

Unknown if it isn't a list.
"""

from __future__ import annotations

from proki.core.ops.base import Operand
from proki.core.ops.lift import Lift


class Len(Lift):
    USAGE = "len(xs)"
    ABOUT = "how many items a list has"

    def __init__(self, xs: Operand):
        super().__init__(lambda v: len(v) if isinstance(v, list | tuple) else None, xs, type="integer")
