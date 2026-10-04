"""Variables: app state, a value something sets (an action, a flow), not read from the
world or computed from other streams.

A `Variable` is a stream whose value is whatever it was last set to: `set`, `add` and
`sub` change it (between cycles too: a reader in the same cycle sees the new value), and
every cycle reads it like a primitive, so expressions can use it (`time - last_suggested`).

Its starting `value` is a constant (a number, true / false, null) or an expression,
worked out once on its first cycle: `"time - clock + 1440"` is the next midnight. Every
variable keeps its latest value in `Variable.store` (a key-value store), saved when it
changes and read back when it's made, so it carries on after a restart; the starting
value counts only while nothing is saved (or what's saved is of another kind than a
constant starting value: a number where text is expected). Resetting is up to flows
(`{"set": {"daily_metric": 0}}` when a day ends), not the variable.

An `Update` is a change written in the config: `set`, `add` or `sub` of one or more
variables, each by an expression's value at the moment it's applied:
`{"set": {"deadline_eod": "deadline_eod + 1440", "daily_metric": 0}}`. Its expressions
are hidden signals (made up front, so their windows move on every cycle), all worked out
before any is assigned (`{"set": {"a": "b", "b": "a"}}` swaps them).
"""

from __future__ import annotations

import itertools
from datetime import datetime
from typing import Any, ClassVar, Protocol

from proki.core.signals.base import Signal, Stream
from proki.utils import kind, same

OPS = ("set", "add", "sub")


class VariableStore(Protocol):
    """Where variables keep their latest value, by name (the app gives one: core/store.py)."""

    def load(self, name: str) -> Any: ...  # raises KeyError if it was never saved
    def save(self, name: str, value: Any) -> None: ...


class Variable(Stream):
    store: ClassVar[VariableStore | None] = None

    def __init__(self, name: str, value: Any = None):
        if not name:    raise ValueError("variable name can't be empty")
        self.name = name
        self.value: Any = None if isinstance(value, str) else value
        self.start: Signal | None = None  # a starting expression, until its first cycle
        Stream.registry[name] = self

        if self._saved(value):
            return
        if isinstance(value, str):
            self.start = Signal(f"{name}.value", value)  # its names are looked up on its first cycle
            self.inputs = [self.start]  # worked out before it, in its first cycle

    def _saved(self, start: Any) -> bool:
        """Take the saved value, if there is one of the right kind."""
        if Variable.store is None:
            return False
        try:
            saved = Variable.store.load(self.name)
        except KeyError:
            return False
        if not isinstance(start, str) and None not in (start, saved) and kind(start) != kind(saved):
            return False  # the config changed what it holds
        self.value = saved
        return True

    def advance(self, t: datetime) -> None:
        super().advance(t)
        if self.start is not None:  # its first cycle: the starting expression, once
            start, self.start, self.inputs = self.start, None, []
            del Stream.registry[start.name]
            self._keep(start.current())

    def compute(self) -> Any:
        return self.value

    def set(self, value: Any) -> None:
        if not same(value, self.value):
            self._keep(value)
        self._cached = False

    def add(self, amount: Any) -> None:
        """Add `amount`; an unknown amount or value (None) changes nothing."""
        if self.value is not None and amount is not None:
            self.set(self.value + amount)

    def sub(self, amount: Any) -> None:
        if self.value is not None and amount is not None:
            self.set(self.value - amount)

    def _keep(self, value: Any) -> None:
        self.value = value
        if Variable.store is not None:
            Variable.store.save(self.name, value)

    def __repr__(self) -> str:
        return f"<Variable {self.name} = {self.value!r}>"


class Update:
    """`op` (set, add, sub) of each variable in `changes` by its expression's value when
    applied (null: unknown)."""

    _ids: ClassVar[itertools.count] = itertools.count(1)

    def __init__(self, op: str, changes: dict[str, str | float | bool | None]):
        if op not in OPS:
            raise ValueError(f"an update is one of {', '.join(OPS)} ({op!r})")
        if not changes:
            raise ValueError(f"{op} what? ({{\"{op}\": {{variable: expr}}}})")
        self.op = op
        self.changes: list[tuple[Variable, Signal | None]] = []
        for name, expr in changes.items():
            target = Stream.registry.get(name)
            if not isinstance(target, Variable):
                raise ValueError(f"no variable is called {name!r}")
            value = None
            if expr is not None:
                value = Signal(f"{name}.{op}.{next(Update._ids)}", str(expr))
                value.inputs  # every name it reads is defined
            self.changes.append((target, value))

    def apply(self) -> None:
        values = [value.current() if value else None for _, value in self.changes]  # all first
        for (variable, _), v in zip(self.changes, values):
            getattr(variable, self.op)(v)

    def __repr__(self) -> str:
        changes = ", ".join(f"{v.name}: {e.expr if e else None}" for v, e in self.changes)
        return f"<Update {self.op} {{{changes}}}>"
