"""where(xs, keep): a list's items whose `keep`, a list as long (a column), is known and not
false. where(xs, keys, x): its items whose `keys` is x.

    where(work.tasks, work.tasks.start)           the tasks to start now
    where(work.tasks, work.tasks.group, 3)        group 3's tasks

Unknown if they aren't lists as long.
"""

from __future__ import annotations

from typing import Any

from proki.core.ops.base import Operand
from proki.core.ops.lift import Lift


class Where(Lift):
    USAGE = "where(xs, keep)"
    ABOUT = "a list's items whose keep, a column, is known and not false (where(tasks, tasks.start)), or is x: where(xs, keys, x)"

    def __init__(self, xs: Operand, keep: Operand, *x: Operand):
        super().__init__(kept, xs, keep, *x, unknown=True, type=lambda of: of(self.inputs[0]))


def kept(value: Any, keep: Any, *x: Any) -> list | None:
    """`value`'s items whose `keep` is known and not false, or is x (none: not lists, or not as long)."""
    if not isinstance(value, list | tuple) or not isinstance(keep, list | tuple) or len(keep) != len(value):
        return None
    return [item for item, k in zip(value, keep) if (k == x[0] if x else k is not None and k is not False)]
