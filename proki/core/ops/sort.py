"""sort(xs): a list's items, least first. sort(xs, keys): its items in the order of `keys`, a
list as long (a column).

    sort(tasks, tasks.deadline)       the tasks, the one due first first

Unknown items or keys go last, in their order. Unknown if `keys` isn't as long.
"""

from __future__ import annotations

from typing import Any

from proki.core.ops.base import Operand, known
from proki.core.ops.lift import Lift


class Sort(Lift):
    USAGE = "sort(xs, keys)"
    ABOUT = "a list's items, least first: by their own, or by keys, a column (sort(tasks, tasks.deadline))"

    def __init__(self, xs: Operand, keys: Operand | None = None):
        super().__init__(ordered, *([xs] if keys is None else [xs, keys]), type=lambda of: of(self.inputs[0]))


def ordered(value: Any, keys: Any = None) -> list | None:
    """`value`'s items by theirs, or by `keys`'s (none: not lists, or not as long)."""
    keys  = value if keys is None else keys
    items = known(keys)
    if items is None or not isinstance(value, list | tuple) or len(keys) != len(value):
        return None
    first = [i for i, _ in sorted(items, key=lambda iv: iv[1])]
    return [value[i] for i in first] + [value[i] for i in range(len(value)) if keys[i] is None]
