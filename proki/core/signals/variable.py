"""Variables: app state, a value that actions or programs set, rather than one read from
the world or worked out from other streams. Examples: in_session, deadline_eod, task.

    {"name": "deadline_eod", "value": "time - clock + 1440"}

Reading: a variable is a stream like any other, so expressions can use it
(`time - last_suggested`). Its value is whatever it was last set to.

Changing: `set`, `add` and `sub` (the config's set / add / sub actions, core/actions/var/).
A change shows at once, even within the same cycle.

Starting value: a constant (a number, true / false, null) or an expression. Text is
always read as an expression, so `"time - clock + 1440"` means "next midnight". The
expression is worked out once, on the first live cycle (not while the startup replays
the past). Until then the variable is unknown.

Saved across restarts: every change is saved (`Variable.store`) and read back when the
variable is made, so a saved value replaces the starting value. If the config now
starts it with a different kind of value (a number where it was text), the saved value
is dropped. Resetting a variable (each day, say) is up to programs, not the variable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Protocol

from proki.core.signals.signal import Signal
from proki.core.signals.stream import Stream
from proki.utils import kind, same
from proki.errors import VariableError

class VariableStore(Protocol):
    """Where variables save their latest value, by name. The app provides one."""

    def load(self, name: str) -> Any: ...  # raises KeyError if it was never saved
    def save(self, name: str, value: Any) -> None: ...


class Variable(Stream):
    """App state: a value set by actions, saved across restarts."""

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
        """Use the saved value, if there is one and it's the same kind as the starting
        value. Returns True if it did."""
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
        """Change the value (and save it). Everything reading it sees the new value at once."""
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

    def _keep(self, value: Any) -> None:
        self.value = value
        if Variable.store is not None:
            Variable.store.save(self.name, value)

    def __repr__(self) -> str:
        return f"<Variable {self.name} = {self.value!r}>"
