"""lift(f, x, y, ...): f applied to the inputs' values, each cycle. Expressions use it for
+ - * /, comparisons and and / or / not.

If any input is unknown, the result is unknown (unless `f` handles unknown values itself,
like and / or). If `f` fails on the values (text where a number goes, `app > 3`), the
result is unknown too, rather than the cycle failing. Plain values count as constants.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from proki.core.ops.base import (
    Operand,
    Operator,
    as_stream
)


class Lift(Operator, function=False):  # reached through + - * /, comparisons, and / or / not
    def __init__(self, f: Callable[..., Any], *xs: Operand, unknown: bool = False):
        self.f, self.inputs = f, [as_stream(x) for x in xs]
        self.unknown = unknown  # True: `f` gets unknown values and decides itself (and / or)

    def advance(self, t: datetime) -> None:
        super().advance(t)
        periods = [x.period for x in self.inputs]
        self.period = None if None in periods else min(periods)  # as fast as its fastest input
        self.fresh = any(x.fresh for x in self.inputs)

    def compute(self) -> Any:
        values = [x.current() for x in self.inputs]
        if not self.unknown and any(v is None for v in values):
            return None
        try:
            return self.f(*values)
        except (TypeError, ValueError, ArithmeticError):  # `app > 3`: unknown, not a failed cycle
            return None
