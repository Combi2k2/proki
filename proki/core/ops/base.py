"""What the operators share: the `Operator` base (which names each one for expressions),
constants, and `Queued`, the (time, value) queue the window operators keep."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from typing import Any, ClassVar

from proki.core.signals.stream import NEVER, Stream
from proki.utils import snake

Operand = Stream | float | int | bool | str | None


class Operator(Stream):
    """An operator: Python calls the class (`TsMean(keys, 5)`), an expression its name in
    snake case (`ts_mean(keys, 5)`). Defining a subclass registers it in `functions`
    (`function=False`: a base or an internal one, not called by name)."""

    functions: ClassVar[dict[str, type[Operator]]] = {}

    def __init_subclass__(cls, function: bool = True, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        if function:
            Operator.functions[snake(cls.__name__)] = cls


class Constant(Stream):
    period = NEVER
    fresh = False

    def __init__(self, value: Any):
        self.constant = value

    def compute(self) -> Any:
        return self.constant


def as_stream(x: Operand) -> Stream:
    return x if isinstance(x, Stream) else Constant(x)


class Queued(Operator, function=False):
    """Takes its input's fresh values into a queue of (time, value); the first time, it
    fills the queue from the input's table over the last `span` (if it keeps one)."""

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
        self.queue.append((t, v))

    def drop(self, before: datetime) -> None:
        """Let go of what is no longer needed (at or before `before`, for a window)."""
        while self.queue and self.queue[0][0] <= before:
            self.pop(self.queue.popleft())

    def pop(self, row: tuple[datetime, Any]) -> None:
        pass
