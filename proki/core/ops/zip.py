"""zip(xs, ys, ...): lists side by side, a list of their items at each place, as long as the
shortest.

    zip(groups.name, groups.desc)     each group's [name, desc] (a question's options)

Unknown if one isn't a list.
"""

from __future__ import annotations

from typing import Any

from proki.core.ops.base import Operand
from proki.core.ops.lift import Lift
from proki.types import itemof, listof


class Zip(Lift):
    USAGE = "zip(xs, ys, ...)"
    ABOUT = "lists side by side: zip(groups.name, groups.desc), each group's [name, desc]"

    def __init__(self, *xs: Operand):
        super().__init__(lambda *vs: [list(row) for row in zip(*vs)] if all(isinstance(v, list | tuple) for v in vs) else None,
                         *xs, type=lambda of: rows(self, of))


def rows(op: Lift, of: Any) -> Any:
    """What zip gives: lists of its lists' items, of their type if they share one."""
    items = {str(itemof(of(x))) for x in op.inputs}
    return listof(listof(itemof(of(op.inputs[0])) if len(items) == 1 else "any"))
