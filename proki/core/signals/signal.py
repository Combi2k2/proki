"""Signals: a name and a time-series expression over other streams (expr.py). The
expression compiles into a tree of streams on the first cycle after the signal is made,
so it may name streams made after it; a signal can keep a table of its history
(`backfill`, `window`) and save it (`persist`).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from proki.core.signals.expr import compile_expr, parse
from proki.core.signals.stream import Stream
from proki.errors import SignalError


class Signal(Stream):
    def __init__(self, name: str, expr: str, backfill: bool = False, window: timedelta | None = None,
                 persist: bool = False):
        if not name:    raise SignalError("signal name can't be empty")
        if not expr:    raise SignalError("signal expr can't be empty")
        if persist and (not backfill or window is None):
            raise SignalError("a persisted signal keeps a table of a window: it needs backfill=True and a window")

        parse(expr)  # a syntax error shows now; unknown names on the first cycle

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
