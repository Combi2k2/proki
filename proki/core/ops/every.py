"""every(x, p, how): x at a slower pace, one value per p minutes, on your clock: every(x, 60)
on the hour, every(x, 1440) at midnight, every(x, 10080) on Monday.

    every(focus, 5)                   the average focus of each 5 minutes
    every(keys, 60, "sum")            key presses per hour

`how` makes a span's known values one: "mean" (the default) or "sum" of numbers, "max",
"min" or "last" of anything comparable. Each value holds until the next span ends; unknown
after a span with none.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.ops.base import Operand, Operator, as_stream
from proki.core.signals.stream import Stream
from proki.errors import ExprError
from proki.utils import span

MONDAY = datetime(2000, 1, 3)  # a Monday at midnight: spans are counted from it, on the local clock
HOWS   = ("mean", "sum", "max", "min", "last")


class Every(Operator):
    USAGE = "every(x, p, how)"
    ABOUT = 'one value per p minutes: the "mean" (default), "sum", "max", "min" or "last"'
    keeps = True

    def __init__(self, x: Operand, p: float, how: str = "mean"):
        if how not in HOWS:  raise ExprError(f"every: `how` is one of {', '.join(HOWS)}, not {how!r}")
        self.inputs, self.period, self.how = [as_stream(x)], span(p), how
        if how in ("last", "max", "min"):  # one of its input's values: its type
            self._typed, self._infer = None, lambda of: of(self.inputs[0])
        self.span : int | None = None   # the span being collected, by its number
        self.value: Any = None
        self.reset()

    def reset(self) -> None:
        self.n, self.total, self.top, self.bottom, self.last = 0, 0.0, None, None, None

    def advance(self, t: datetime) -> None:
        super().advance(t)
        span = (t.astimezone().replace(tzinfo=None) - MONDAY) // self.period
        self.fresh = self.span is not None and span != self.span
        if self.fresh:  # a span over: its values made one
            self.value = self.made() if self.n else None
            self.reset()
        self.span = span
        x = self.inputs[0]
        v = x.current() if x.fresh else None
        if v is not None:
            self.n += 1
            if self.how in ("mean", "sum"):
                self.total += float(v)
            self.top    = v if self.top is None or v > self.top else self.top
            self.bottom = v if self.bottom is None or v < self.bottom else self.bottom
            self.last   = v

    def made(self) -> Any:
        """A span's values, made one as `how` says."""
        match self.how:
            case "mean":  return self.total / self.n
            case "sum":   return self.total * (self.inputs[0].period or Stream.cycle).total_seconds() / 60  # as ts_sum
            case "max":   return self.top
            case "min":   return self.bottom
        return self.last

    def compute(self) -> Any:
        return self.value
