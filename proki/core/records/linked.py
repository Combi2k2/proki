"""A name a program reads and sets as a variable, linked to a value held elsewhere: read, it's
that value as it is now; set, that value is set (one with nowhere to set it: read only).

    Linked("work.plan", plan.read, plan.write, "the plan", PLAN)

    work.plan.name                      the plan's name, as the plan has it now
    work.plan.name = 'Thesis'           the plan's name, changed in the plan
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from proki.core.signals import Variable
from proki.errors import VariableError
from proki.types import Type, oftype, typename


class Linked(Variable):
    """A name linked to a value held elsewhere: `read()` gives it, `write(value)` sets it (None:
    read only). VariableError for a value not of its type."""

    def __init__(self, name: str, read: Callable[[], Any], write: Callable[[Any], None] | None = None, desc: str = "", type: Type = "any"):
        super().__init__(name, None, desc, type=type)
        self.read, self.write = read, write

    def compute(self) -> Any:
        return self.read()

    def set(self, value: Any) -> None:
        if not self.write:                  raise VariableError(f"{self.name} is read only")
        if not oftype(value, self._typed):  raise VariableError(f"{self.name} is of type {typename(self._typed)} ({value!r})")
        self.write(value)

    def reset(self) -> None:
        pass  # held where it's linked to: a program starting over doesn't change it
