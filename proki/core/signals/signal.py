"""Signals: a name for an expression, so other expressions, rules and programs can use it.

    {"name": "focus_5m", "expr": "ts_mean(focus, 5)"}

The expression is compiled (expr.py) the first time it's needed, so it may use names
defined after it. A signal can keep a table of its past values (`backfill`), how far
back (`window`) and save it to disk (`persist`).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from proki.core.signals.expr import compile_expr, parse
from proki.core.signals.stream import Stream
from proki.errors import SignalError


class Signal(Stream):
    """A named expression. Its value each cycle is the expression's."""

    def __init__(self, name: str, expr: str, backfill: bool = False, window: timedelta | None = None,
                 persist: bool = False):
        if not name:    raise SignalError("signal name can't be empty")
        if not expr:    raise SignalError("signal expr can't be empty")
        if persist and (not backfill or window is None):
            raise SignalError("a persisted signal keeps a table of a window: it needs backfill=True and a window")

        parse(expr)  # a syntax error shows now, an unknown name only once it's compiled

        self.name = name
        self.expr = expr  # e.g. "ts_mean(keys, 5)"
        self.backfill = backfill
        self.window = window
        self.persist = persist
        self._tree: Stream | None = None
        Stream.registry[name] = self

    @property
    def inputs(self) -> list[Stream]:  # type: ignore[override]
        if self._tree is None:
            self._tree = compile_expr(self.expr)
        return [self._tree]

    def advance(self, t: datetime) -> None:
        super().advance(t)
        self.period, self.fresh = self.inputs[0].period, self.inputs[0].fresh

    def compute(self) -> Any:
        return self.inputs[0].current()

    def __repr__(self) -> str:
        return f"<Signal {self.name} = {self.expr}>"
