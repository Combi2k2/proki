"""Variables: app state, a value something sets (an action, a flow), not read from the
world or computed from other streams.

A `Variable` is a stream whose value is whatever it was last set to: `set`, `add` and
`sub` change it (between cycles too: a reader in the same cycle sees the new value), and
every cycle reads it like a primitive, so expressions can use it (`time - last_suggested`).

Its starting `value` is a constant (a number, true / false, null) or an expression,
worked out once on its first live cycle (not while the startup replays the past; it's
unknown till then): `"time - clock + 1440"` is the next midnight. Every
variable keeps its latest value in `Variable.store` (a key-value store), saved when it
changes and read back when it's made, so it carries on after a restart; the starting
value counts only while nothing is saved (or what's saved is of another kind than a
constant starting value: a number where text is expected). Resetting is up to flows
(`{"set": {"daily_metric": 0}}` when a day ends), not the variable.
The config changes one with the set / add / sub actions (core/actions/), each by an
expression's value at the moment.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Protocol

from proki.core.signals.signal import Signal
from proki.core.signals.stream import Stream
from proki.utils import kind, same
from proki.errors import VariableError

class VariableStore(Protocol):
    """Where variables keep their latest value, by name (the app gives one: core/store.py)."""

    def load(self, name: str) -> Any: ...  # raises KeyError if it was never saved
    def save(self, name: str, value: Any) -> None: ...


class Variable(Stream):
    store: ClassVar[VariableStore | None] = None

    def __init__(self, name: str, value: Any = None):
        if not name:    raise VariableError("variable name can't be empty")
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
        if self.start is not None and (Stream.live is None or t + Stream.cycle > Stream.live):  # its first live cycle: the starting expression, once
            start, self.start, self.inputs = self.start, None, []
            del Stream.registry[start.name]
            self._keep(start.current())

    def compute(self) -> Any:
        return self.value

    def set(self, value: Any) -> None:
        if not same(value, self.value):
            self._keep(value)
            Stream.epoch += 1  # what was worked out from it this cycle is stale

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
