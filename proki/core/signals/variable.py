"""Variables: state a program keeps, a value its actions set rather than one read from the
world or worked out from other streams.

    {"name": "pokes", "value": 0}
    {"name": "deadline", "value": "now + 60"}

A variable is a stream like any other, so expressions read it (`deadline - now`). Over its
life, it:

    starts      at its starting value: a constant (a number, true / false, null), or an
                expression (text is always one: "now + 60"), worked out once, on the first
                live cycle, not while the past is caught up on. Until then it's unknown
    changes     as it's set, added to or subtracted from. What reads it sees the change at
                once, within the same cycle too
    resets      back to its starting value, as its program starts over or its state is left
    persists    with `persist`, each change is saved (`Variable.store`) and read back as it's
                made: a saved value takes the starting value's place, unless it's of another
                kind than the one it starts as (a number, where it now starts as text). A
                global variable persists; a program's or a state's doesn't

Its type is as it says, else what it starts as (an expression's, worked out once all is
built), or what an answer into it is (`take`). A value set that isn't of it is refused.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Protocol

from proki.core.signals.expr import compile_expr
from proki.core.signals.signal import Signal
from proki.core.signals.stream import Stream
from proki.core.signals.types import accept, oftype, typename, typeof
from proki.errors import VariableError
from proki.utils import same


class VariableStore(Protocol):
    """Where variables save their latest value, by name. The app provides one."""

    def load(self, name: str) -> Any: ...  # KeyError if it was never saved
    def save(self, name: str, value: Any) -> None: ...


class Variable(Stream):
    """State a program keeps (see above): set by its actions, saved across restarts if it `persist`s."""

    store: ClassVar[VariableStore | None] = None  # where persisted variables are saved

    def __init__(self, name: str, value: Any = None, desc: str = "", persist: bool = False, type: str | dict = "any"):
        if not name:    raise VariableError("variable name can't be empty")

        self.name = name
        self.desc = desc
        self.declared = type not in (None, "any")
        self.given: str | dict | None = None  # the type of what's answered into it (`take`)
        self._typed  = type if self.declared else None if isinstance(value, str) else typeof(value)  # as it says, else what it starts as
        self.persist = persist
        self.initial = value  # its starting value: a constant, or an expression
        self.value: Any = None if isinstance(value, str) else value
        self.start: Signal | None = None  # its starting expression, until its first live cycle
        Stream.registry[name] = self

        if persist and self._saved(value):
            if self._typed is None:
                self._typed = typeof(self.value)  # as it was kept
            return
        if isinstance(value, str):
            self.start = Signal(f"{name}.value", value)  # its names are looked up on its first cycle
            self.inputs = [self.start]  # worked out before it, in that cycle
            if not self.declared:  # what it starts as: its expression's
                self._infer = lambda of, start=self.start: of(start)

    def advance(self, t: datetime) -> None:
        super().advance(t)
        first_live = Stream.live is None or t + Stream.cycle > Stream.live
        if self.start is not None and first_live:  # the starting expression, once
            start, self.start, self.inputs = self.start, None, []
            del Stream.registry[start.name]
            self._keep(start.current())

    def compute(self) -> Any:
        return self.value

    def take(self, type: Any) -> None:
        """The type of what's answered into it (a question's answer), as its own: VariableError
        for one its own type doesn't accept, or one of another type than an answer before."""
        if self.declared:
            if not accept(self._typed, type):  raise VariableError(f"{self.name} is of type {typename(self._typed)}: the answer is {typename(type)}")
            return
        if self.given is not None and self.given != type:
            raise VariableError(f"{self.name} is answered as {typename(self.given)} already: this answer is {typename(type)}")
        self.given = self._typed = type
        self._infer = None

    def set(self, value: Any) -> None:
        """Change the value (saved, if it persists). What reads it sees the new value at once.
        VariableError for a value not of its type."""
        if not oftype(value, self._typed):
            raise VariableError(f"{self.name} is of type {typename(self._typed)} ({value!r})")
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
        if not isinstance(start, str) and None not in (start, saved) and typename(typeof(start)) != typename(typeof(saved)):
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
