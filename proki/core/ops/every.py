"""every(x, p, how): x at a slower pace, one value per p minutes.

    every(focus, 5)          the average focus of each 5 minutes
    every(keys, 60, "sum")   key presses per hour

`how` is how a span's values become one: "mean" (default), "sum", "max", "min" or "last".
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.ops.base import Operand, Operator, as_stream
from proki.core.signals.stream import Stream
from proki.errors import ExprError
from proki.utils import minutes

EPOCH = datetime(2000, 1, 3)  # a Monday at midnight: spans are counted from here, on the local clock


class Every(Operator):
    """x at one value per `p` minutes.

    Time is cut into spans of `p` minutes on the local clock: every(x, 60) spans start on
    the hour, every(x, 1440) at midnight where you are, every(x, 10080) on Monday. While a
    span runs, x's known values are collected. When it ends, they become one value (`how`)
    and it's fresh on that cycle. The value holds until the next span ends. Unknown if
    a span had no known values.

    "mean" and "sum" need numbers. "max", "min" and "last" take anything comparable, text too."""

    HOWS = ("mean", "sum", "max", "min", "last")

    def __init__(self, x: Operand, p: float, how: str = "mean"):
        if how not in self.HOWS:
            raise ExprError(f"every: `how` is one of {', '.join(self.HOWS)}, not {how!r}")
        self.inputs, self.period, self.how = [as_stream(x)], minutes(p), how
        self.span: int | None = None  # the span being collected (its number since EPOCH)
        self.value: Any = None
        self._reset()

    def _reset(self) -> None:
        self.n, self.total, self.top, self.bottom, self.last = 0, 0.0, None, None, None

    def advance(self, t: datetime) -> None:
        super().advance(t)
        span = (t.astimezone().replace(tzinfo=None) - EPOCH) // self.period  # on the local clock
        self.fresh = self.span is not None and span != self.span
        if self.fresh:
            self.value = None if not self.n else {
                "mean": self.total / self.n,
                "sum": self.total * (self.inputs[0].period or Stream.cycle).total_seconds() / 60,  # like ts_sum
                "max": self.top,
                "min": self.bottom,
                "last": self.last,
            }[self.how]
            self._reset()
        self.span = span
        x = self.inputs[0]
        v = x.current() if x.fresh else None
        if v is not None:
            self.n += 1
            if self.how in ("mean", "sum"):
                self.total += float(v)
            self.top = v if self.top is None or v > self.top else self.top
            self.bottom = v if self.bottom is None or v < self.bottom else self.bottom
            self.last = v

    def compute(self) -> Any:
        return self.value
