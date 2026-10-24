"""Variables: a value that's set, by a program's actions or by you, not read from the world
or worked out from other streams.

    {"name": "pokes", "value": 0}
    {"name": "deadline", "value": "now + 60"}

Expressions read it as any stream (`deadline - now`). Over its life, it:

    starts      at its starting value: a constant (a number, true / false, null), or an
                expression (text always is: "now + 60"), worked out as proki starts on the
                present, not while it catches up on the past. Until then it's unknown
    changes     as it's set, added to or taken from: read as it is at once, and by what's
                worked out from it from the next cycle on
    resets      back to its starting value, as its program starts over or its state is left
    persists    with `persist` (a global one does; a program's or a state's doesn't), it's
                there again after a restart, unless it now starts as another kind of value

Its type is as it says, else what it starts as, or what's answered into it. A value set that
isn't of it is refused.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Protocol

from proki.core.signals.expr import compile_expr
from proki.core.signals.signal import Signal
from proki.core.signals.stream import Stream
from proki.types import accept, oftype, typename, typeof
from proki.errors import VariableError
from proki.utils import same


class VariableStore(Protocol):
    """Where the variables that persist save their value, by name. The app gives one."""

    def load(self, name: str, type: str | dict | None = None) -> Any: ...  # KeyError if it was never saved
    def save(self, name: str, value: Any, type: str | dict | None = None) -> None: ...  # `type`: how it's kept


class Variable(Stream):
    """A value that's set (see above), there again after a restart if it `persist`s."""

    store: ClassVar[VariableStore | None] = None  # where the ones that persist are saved

    def __init__(self, name: str, value: Any = None, desc: str = "", persist: bool = False, type: str | dict = "any"):
        if not name:
            raise VariableError("variable name can't be empty")

        self.name, self.desc, self.persist = name, desc, persist
        self.declared = type not in (None, "any")
        self.given    : str | dict | None = None   # the type of what's answered into it (`take`)
        self._typed   = type if self.declared else None if isinstance(value, str) else typeof(value)  # as it says, else what it starts as
        self.initial  = value                      # its starting value: a constant, or an expression
        self.value    : Any = None if isinstance(value, str) else value
        self.start    : Signal | None = None       # its starting expression, until it's worked out
        Stream.registry[name] = self

        if persist and self._load(value):
            if self._typed is None:
                self._typed = typeof(self.value)  # as it was kept
            return
        if isinstance(value, str):
            self.start  = Signal(f"{name}.value", value)  # its names looked up as it's first read
            self.inputs = [self.start]                     # worked out before it
            if not self.declared:  # what it starts as: its expression's
                self._infer = lambda of, start=self.start: of(start)

    def advance(self, t: datetime) -> None:
        super().advance(t)
        present = Stream.live is None or t + Stream.cycle > Stream.live
        if self.start is not None and present:  # the starting expression, once
            start, self.start, self.inputs = self.start, None, []
            del Stream.registry[start.name]
            self._keep(start.current())

    def current(self) -> Any:
        return self.compute()  # as it is, at once

    def compute(self) -> Any:
        return self.value

    def take(self, type: Any) -> None:
        """The type of what's answered into it, as its own. VariableError for one its own type
        doesn't take, or one other than an answer's before."""
        if self.declared:
            if not accept(self._typed, type):  raise VariableError(f"{self.name} is of type {typename(self._typed)}: the answer is {typename(type)}")
            return
        if self.given is not None and self.given != type:
            raise VariableError(f"{self.name} is answered as {typename(self.given)} already: this answer is {typename(type)}")
        self.given = self._typed = type
        self._infer = None

    def set(self, value: Any) -> None:
        """Its value from now on. VariableError for one not of its type."""
        if not oftype(value, self._typed):
            raise VariableError(f"{self.name} is of type {typename(self._typed)} ({value!r})")
        if not same(value, self.value):
            self._keep(value)

    def add(self, amount: Any) -> None:
        """`amount` added (either unknown: as it is)."""
        if self.value is not None and amount is not None:
            self.set(self.value + amount)

    def sub(self, amount: Any) -> None:
        """`amount` taken from it (either unknown: as it is)."""
        if self.value is not None and amount is not None:
            self.set(self.value - amount)

    def reset(self) -> None:
        """Back to its starting value: the constant, or the expression as it reads now (not
        started yet: as it is)."""
        if self.start is None:
            self.set(compile_expr(self.initial).current() if isinstance(self.initial, str) else self.initial)

    def _load(self, start: Any) -> bool:
        """Whether it took its saved value: one of the kind it starts as."""
        if Variable.store is None:
            return False
        try:
            saved = Variable.store.load(self.name, self._typed)
        except KeyError:
            return False
        if not isinstance(start, str) and None not in (start, saved) and typename(typeof(start)) != typename(typeof(saved)):
            return False  # the config changed what it holds
        self.value = saved
        return True

    def _keep(self, value: Any) -> None:
        """`value` held, and saved if it persists."""
        self.value = value
        if self.persist and Variable.store is not None:
            Variable.store.save(self.name, value, self._typed)

    def __repr__(self) -> str:
        return f"<Variable {self.name} = {self.value!r}>"
