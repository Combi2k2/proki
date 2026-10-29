"""+ - * / // %, comparisons, and / or / not: each of their values, each cycle.

Unknown if any value is (but `True or unknown` is True, `False and unknown` False), or if
they can't be worked out together: text where a number goes (`app > 3`), a division by zero.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from proki.core.ops.base import Operand, Operator, as_stream


class Lift(Operator, function=False):
    def __init__(self, f: Callable[..., Any], *xs: Operand, unknown: bool = False, type: Any = "any"):
        self.f, self.inputs = f, [as_stream(x) for x in xs]
        self.unknown = unknown  # whether `f` reads unknown values itself (and / or)
        self._typed, self._infer = (None, type) if callable(type) else (type, None)  # what `f` gives: a type, or how it's worked out

    def advance(self, t: datetime) -> None:
        super().advance(t)
        periods     = [x.period for x in self.inputs]
        self.period = None if None in periods else min(periods)  # as fast as its fastest input
        self.fresh  = any(x.fresh for x in self.inputs)

    def compute(self) -> Any:
        values = [x.current() for x in self.inputs]
        if not self.unknown and any(v is None for v in values):
            return None
        try:
            return self.f(*values)
        except (TypeError, ValueError, ArithmeticError):  # `app > 3`: unknown, not a failed cycle
            return None
