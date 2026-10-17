"""Variables: app state, a value that actions or programs set, rather than one read from
the world or worked out from other streams. Examples: in_session, deadline_eod, task.

    {"name": "deadline_eod", "value": "time - clock + 1440"}

A variable is a stream like any other, so expressions read it (`time - last_suggested`).
What it does over its life:

    starts      at its starting value: a constant (a number, true / false, null) or an
                expression. Text is always an expression, so "time - clock + 1440" means
                the next midnight. An expression is worked out once, on the first live
                cycle (not while the startup replays the past). Until then it's unknown
    changes     by `set`, `add` and `sub` (the config's actions, core/actions/var.py). A
                change shows at once, even within the same cycle
    resets      back to its starting value (`reset`). A program resets its own variables
                when it starts over, and a state's when it's left (core/programs.py)
    persists    with `persist`, every change is saved (`Variable.store`) and read back when
                it's made, so a saved value replaces the starting value. A saved value of
                another kind (a number where the config now starts it with text) is
                dropped. The builder (model/) makes every global variable persist, and no
                program's or state's
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Protocol

from proki.core.signals.expr import compile_expr
from proki.core.signals.signal import Signal
from proki.core.signals.stream import Stream
from proki.errors import VariableError
from proki.typehint import typeof
from proki.utils import same


class VariableStore(Protocol):
    """Where variables save their latest value, by name. The app provides one."""

    def load(self, name: str) -> Any: ...  # KeyError if it was never saved
    def save(self, name: str, value: Any) -> None: ...


class Variable(Stream):
    """App state: a value set by actions, saved across restarts if it `persist`s."""

    store: ClassVar[VariableStore | None] = None  # where persisted variables are saved

    def __init__(self, name: str, value: Any = None, desc: str = "", persist: bool = False):
        if not name:    raise VariableError("variable name can't be empty")

        self.name = name
        self.desc = desc
        self.persist = persist
        self.initial = value  # its starting value: a constant, or an expression
        self.value: Any = None if isinstance(value, str) else value
        self.start: Signal | None = None  # its starting expression, until its first live cycle
        Stream.registry[name] = self

        if persist and self._saved(value):
            return
        if isinstance(value, str):
            self.start = Signal(f"{name}.value", value)  # its names are looked up on its first cycle
            self.inputs = [self.start]  # worked out before it, in that cycle

    def advance(self, t: datetime) -> None:
        super().advance(t)
        first_live = Stream.live is None or t + Stream.cycle > Stream.live
        if self.start is not None and first_live:  # the starting expression, once
            start, self.start, self.inputs = self.start, None, []
            del Stream.registry[start.name]
            self._keep(start.current())

    def compute(self) -> Any:
        return self.value

    def set(self, value: Any) -> None:
        """Change the value (saved, if it persists). What reads it sees the new value at once."""
        if not same(value, self.value):
            self._keep(value)
            Stream.epoch += 1  # what was worked out from it this cycle is stale

    def add(self, amount: Any) -> None:
        """Add `amount`. If either the amount or the value is unknown, nothing changes."""
        if self.value is not None and amount is not None:
            self.set(self.value + amount)

    def sub(self, amount: Any) -> None:
        """Subtract `amount`. If either the amount or the value is unknown, nothing changes."""
        if self.value is not None and amount is not None:
            self.set(self.value - amount)

    def reset(self) -> None:
        """Back to its starting value: the constant, or the expression worked out now.
        Before its first live cycle it hasn't started, so there's nothing to go back from."""
        if self.start is None:
            self.set(compile_expr(self.initial).current() if isinstance(self.initial, str) else self.initial)

    def _saved(self, start: Any) -> bool:
        """Take the saved value, if there is one of the same kind as `start`. True if it did."""
        if Variable.store is None:
            return False
        try:
            saved = Variable.store.load(self.name)
        except KeyError:
            return False
        if not isinstance(start, str) and None not in (start, saved) and typeof(start) != typeof(saved):
            return False  # the config changed what it holds
        self.value = saved
        return True

    def _keep(self, value: Any) -> None:
        """Hold `value`, and save it if it persists."""
        self.value = value
        if self.persist and Variable.store is not None:
            Variable.store.save(self.name, value)

    def __repr__(self) -> str:
        return f"<Variable {self.name} = {self.value!r}>"
