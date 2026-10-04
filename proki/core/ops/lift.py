"""`f` of the operands' values each cycle; None (unknown) when any of them is. Plain
values count as constant streams."""

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
    def __init__(self, f: Callable[..., Any], *xs: Operand):
        self.f, self.inputs = f, [as_stream(x) for x in xs]

    def advance(self, t: datetime) -> None:
        super().advance(t)
        periods = [x.period for x in self.inputs]
        self.period = None if None in periods else min(periods)  # as fast as its fastest input
        self.fresh = any(x.fresh for x in self.inputs)

    def compute(self) -> Any:
        values = [x.current() for x in self.inputs]
        return None if any(v is None for v in values) else self.f(*values)
