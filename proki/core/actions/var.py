"""Actions on a variable, by an expression's value worked out when the action is taken:

    {"set": {"name": "deadline_eod", "expr": "deadline_eod + 1440"}}   the variable to the value
    {"add": {"name": "active_today", "expr": "active"}}                add the value (true / false add 1 / 0)
    {"sub": {"name": "budget", "expr": "minutes"}}                     subtract the value

`expr` null is unknown. An unknown value added or subtracted changes nothing, and an
unknown variable stays unknown. What they share is `Update`: the variable and the expression.
"""

from __future__ import annotations

from typing import Any

from proki.core.actions.base import Action, check, evaluate
from proki.core.signals import Stream, Variable
from proki.errors import ActionError
from proki.utils import snake


class Update:
    """Mixin: the variable `name`, by the expression `expr`. `change` does what the kind
    does with the expression's value."""

    def __init__(self, name: str, expr: Any):
        kind = snake(type(self).__name__)
        target = Stream.registry.get(name)
        if not isinstance(target, Variable):
            raise ActionError(f"{kind}: no variable is called {name!r}")
        self.variable = target
        self.expr = None if expr is None else str(expr)  # null: unknown
        if self.expr is not None:
            check(self.expr)

    async def apply(self) -> None:
        self.change(None if self.expr is None else evaluate(self.expr))

    def reads(self) -> list[str]:
        return [] if self.expr is None else [self.expr]

    def writes(self) -> list[Variable]:
        return [self.variable]

    def change(self, value: Any) -> None:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{snake(type(self).__name__)} {self.variable.name} by {self.expr}"


class Set(Update, Action):
    def change(self, value: Any) -> None:
        self.variable.set(value)


class Add(Update, Action):
    def change(self, value: Any) -> None:
        self.variable.add(value)


class Sub(Update, Action):
    def change(self, value: Any) -> None:
        self.variable.sub(value)
