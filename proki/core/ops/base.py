"""What each operator builds on, for whoever makes one:

    Operator       an operator, callable in expressions by its name (TsMean: ts_mean)
    Constant       a plain value, as a stream (the 5 in `keys > 5`)
    Queued         a window: its input's values of the last w minutes, full from the start
                   if its input keeps its past
    TsArithmetic   a window of numbers, added up: their total, and how many are known
    TsExtremum     a window's smallest known value, or its largest
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, ClassVar

from proki.core.signals.stream import NEVER, Stream
from proki.types import itemof, typename, typeof
from proki.utils import snake

Operand = Stream | float | int | bool | str | None


class Operator(Stream):
    """An operator, callable in expressions by its name in snake case. `function=False`: one
    expressions don't call by name (a base, or one reached through + - * /)."""

    functions : ClassVar[dict[str, type[Operator]]] = {}
    USAGE     : ClassVar[str] = ""   # how it's called: ts_mean(x, w)
    ABOUT     : ClassVar[str] = ""   # what it gives, in a line
    _typed    = "number"             # most give a number: the others say what they give

    def __init_subclass__(cls, function: bool = True, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        if function:
            Operator.functions[snake(cls.__name__)] = cls


class Constant(Stream):
    """A value that never changes, as a stream."""

    period = NEVER
    fresh  = False

    def __init__(self, value: Any):
        self.constant, self._typed = value, typeof(value)

    def compute(self) -> Any:
        return self.constant


def as_stream(x: Operand) -> Stream:
    return x if isinstance(x, Stream) else Constant(x)


# --- of a list -------------------------------------------------------------------------------

def known(value: Any) -> list[tuple[int, Any]] | None:
    """A list's known items, each with its place (None: it isn't a list)."""
    return [(i, v) for i, v in enumerate(value) if v is not None] if isinstance(value, list | tuple) else None


def least(pick: Callable, *values: Any) -> Any:
    """`pick` (min or max) of the values, or of a list's known items when there's one list."""
    if len(values) == 1 and (items := known(values[0])) is not None:
        return pick((v for _, v in items), default=None)
    return pick(values)


def place(pick: Callable, value: Any) -> int | None:
    """The place of a list's known item `pick` (min or max) gives."""
    return pick(known(value), key=lambda iv: iv[1], default=(None,))[0]


def listed(op: Stream, of: Callable) -> Any:
    """What min or max gives: an item, of one list, else a number."""
    given = of(op.inputs[0])
    return itemof(given) if len(op.inputs) == 1 and typename(given) == "array" else "number"


# --- windows ---------------------------------------------------------------------------------

class Queued(Operator, function=False):
    """A window: the values its input took in the last `span`, the window full from the start
    when its input keeps its past."""

    keeps = True

    def __init__(self, x: Operand, span: timedelta):
        self.inputs, self.span = [as_stream(x)], span
        self.queue: deque[tuple[datetime, Any]] = deque()
        self.started = False

    def advance(self, t: datetime) -> None:
        super().advance(t)
        x = self.inputs[0]
        self.period, self.fresh = x.period, x.fresh
        if not self.started:  # filled from its input's past
            self.started = True
            for when, v in x.history(t - self.span):
                if when < t:
                    self.take(when, v)
        if x.fresh:
            self.take(t, x.current())
        self.drop(t - self.span)

    def take(self, t: datetime, v: Any) -> None:
        """The input's new value `v`, taken at `t`."""
        self.queue.append((t, v))

    def drop(self, before: datetime) -> None:
        """The values taken at or before `before` let go: out of the window."""
        while self.queue and self.queue[0][0] <= before:
            self.pop(self.queue.popleft())

    def pop(self, row: tuple[datetime, Any]) -> None:
        """A value just out of the window."""


class TsArithmetic(Queued, function=False):
    """A window of numbers, added up: their total, and how many are known."""

    def __init__(self, x: Operand, span: timedelta):
        super().__init__(x, span)
        self.total, self.known = 0.0, 0

    def take(self, t: datetime, v: Any) -> None:
        super().take(t, v)
        if v is not None:
            self.total += float(v)
            self.known += 1

    def pop(self, row: tuple[datetime, Any]) -> None:
        if row[1] is not None:
            self.total -= float(row[1])
            self.known -= 1
            if self.known == 0:
                self.total = 0.0  # no rounding drift


class TsExtremum(Queued, function=False):
    """A window's extremum, as `beats` says: its smallest known value (<), or its largest (>)."""

    beats: ClassVar[Callable[[Any, Any], bool]]

    def __init__(self, x: Operand, span: timedelta):
        super().__init__(x, span)
        self.best: deque[tuple[datetime, Any]] = deque()  # the ones that can still be the extremum, it first

    def take(self, t: datetime, v: Any) -> None:
        super().take(t, v)
        if v is None:
            return
        while self.best and type(self).beats(v, self.best[-1][1]):
            self.best.pop()
        self.best.append((t, v))

    def pop(self, row: tuple[datetime, Any]) -> None:
        while self.best and self.best[0][0] <= row[0]:
            self.best.popleft()

    def compute(self) -> Any:
        return self.best[0][1] if self.best else None
