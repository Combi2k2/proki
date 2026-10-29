"""Signals: an expression, named, for other expressions, rules and programs to read.

    {"name": "focus_5m", "expr": "ts_mean(focus, 5)"}

It may read names made after it. It can keep its past (`backfill`), how far back (`window`),
and save it (`persist`).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from proki.core.signals.expr import Expr, parse
from proki.core.signals.stream import Stream
from proki.errors import SignalError


class Signal(Stream):
    """An expression, named: its value each cycle, the expression's."""

    def __init__(self, name: str, expr: str, backfill: bool = False, window: timedelta | None = None, persist: bool = False, desc: str = "",
                 type: str | dict = "any"):
        if not name:                                      raise SignalError("signal name can't be empty")
        if not expr:                                      raise SignalError("signal expr can't be empty")
        if persist and (not backfill or window is None):  raise SignalError("a persisted signal keeps a table of a window: it needs backfill=True and a window")
        parse(expr)  # a syntax error shows now, an unknown name once it's first read

        self.name, self.desc, self.expr = name, desc, expr
        self.backfill, self.window, self.persist = backfill, window, persist
        self._typed, self._infer = (type, None) if type not in (None, "any") else (None, lambda of: of(self.inputs[0]))  # as it says, else its expression's
        self._tree: Stream | None = None
        Stream.registry[name] = self

    @property
    def inputs(self) -> list[Stream]:  # type: ignore[override]
        if self._tree is None:
            self._tree = Expr(self.expr).stream()
        return [self._tree]

    def advance(self, t: datetime) -> None:
        super().advance(t)
        self.period, self.fresh = self.inputs[0].period, self.inputs[0].fresh

    def compute(self) -> Any:
        return self.inputs[0].current()

    def __repr__(self) -> str:
        return f"<Signal {self.name} = {self.expr}>"
