"""every(x, p, how): x resampled to one value per p minutes (clock-aligned spans): the mean
(default), "sum", "max", "min" or "last" of its values in each span."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from proki.core.ops.base import Operand, Operator, as_stream
from proki.core.signals import Stream
from proki.utils import minutes

EPOCH = datetime(2000, 1, 3, tzinfo=timezone.utc)  # a Monday, midnight UTC: spans line up from here


class Every(Operator):
    """`x` resampled: one value per `p` minutes, the `how` (mean, sum, max, min, last) of
    x's known values in each clock-aligned span (None when none was known). It's fresh
    on the first cycle of the next span, and holds the value until the one after."""

    HOWS = ("mean", "sum", "max", "min", "last")

    def __init__(self, x: Operand, p: float, how: str = "mean"):
        if how not in self.HOWS:
            raise ValueError(f"every: `how` is one of {', '.join(self.HOWS)}, not {how!r}")
        self.inputs, self.period, self.how = [as_stream(x)], minutes(p), how
        self.span: int | None = None  # which span the running totals are for
        self.value: Any = None
        self._reset()

    def _reset(self) -> None:
        self.n, self.total, self.top, self.bottom, self.last = 0, 0.0, None, None, None

    def advance(self, t: datetime) -> None:
        super().advance(t)
        span = (t - EPOCH) // self.period
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
            self.total += float(v)
            self.top = v if self.top is None or v > self.top else self.top
            self.bottom = v if self.bottom is None or v < self.bottom else self.bottom
            self.last = v

    def compute(self) -> Any:
        return self.value
