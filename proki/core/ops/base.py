"""What the operators share:

    Operator   the base: defining one names it for expressions (TsMean → ts_mean)
    Constant   a plain value as a stream (the 5 in `keys > 5`)
    Queued     the base of the window operators: a queue of (time, value) of the last w minutes
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from typing import Any, ClassVar

from proki.core.signals.stream import NEVER, Stream
from proki.utils import snake

Operand = Stream | float | int | bool | str | None


class Operator(Stream):
    """An operator. Defining a subclass makes it callable from expressions by its name in
    snake case (`TsMean` → `ts_mean(...)`), via `functions`. Pass `function=False` for a
    base or an internal operator that expressions shouldn't call by name."""

    functions: ClassVar[dict[str, type[Operator]]] = {}

    def __init_subclass__(cls, function: bool = True, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        if function:
            Operator.functions[snake(cls.__name__)] = cls


class Constant(Stream):
    """A value that never changes, as a stream."""

    period = NEVER
    fresh = False

    def __init__(self, value: Any):
        self.constant = value

    def compute(self) -> Any:
        return self.constant


def as_stream(x: Operand) -> Stream:
    return x if isinstance(x, Stream) else Constant(x)


class Queued(Operator, function=False):
    """A window: a queue of (time, value) covering the last `span`.

    Each cycle, if the input took a new value, it's added to the queue. Values older than
    `span` are dropped (`drop`, `pop`). On its first cycle, the queue is filled from the
    input's table, if the input keeps one, so the window starts full. Subclasses keep
    running totals in `take` and `pop` so each cycle costs little."""

    def __init__(self, x: Operand, span: timedelta):
        self.inputs, self.span = [as_stream(x)], span
        self.queue: deque[tuple[datetime, Any]] = deque()
        self.started = False

    def advance(self, t: datetime) -> None:
        super().advance(t)
        x = self.inputs[0]
        self.period = x.period
        self.fresh  = x.fresh
        if not self.started:
            self.started = True
            for when, v in x.history(t - self.span):
                if when < t:
                    self.take(when, v)
        if x.fresh:
            self.take(t, x.current())
        self.drop(t - self.span)

    def take(self, t: datetime, v: Any) -> None:
        """Add the input's new value `v`, taken at time `t`."""
        self.queue.append((t, v))

    def drop(self, before: datetime) -> None:
        """Drop the values at or before time `before` (out of the window)."""
        while self.queue and self.queue[0][0] <= before:
            self.pop(self.queue.popleft())

    def pop(self, row: tuple[datetime, Any]) -> None:
        """A row just left the window (subclasses update their totals here)."""
