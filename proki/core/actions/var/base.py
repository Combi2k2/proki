"""What the variable actions (this folder) share: `Update`, a variable (`name`) and an
expression (`expr`), worked out on the spot when the action is taken."""

from __future__ import annotations

from typing import Any

from proki.core.actions.base import check, evaluate
from proki.core.signals import Stream, Variable
from proki.errors import ActionError
from proki.utils import snake


class Update:
    """Mixin: the variable `name`, by the expression `expr` (null: unknown). `change` does
    what the kind does with the expression's value."""

    def __init__(self, name: str, expr: Any):
        kind = snake(type(self).__name__)
        target = Stream.registry.get(name)
        if not isinstance(target, Variable):
            raise ActionError(f"{kind}: no variable is called {name!r}")
        self.variable = target
        self.expr = None if expr is None else str(expr)  # null: unknown
        if self.expr is not None:
            check(self.expr)

    def apply(self) -> None:
        self.change(None if self.expr is None else evaluate(self.expr))

    def change(self, value: Any) -> None:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{snake(type(self).__name__)} {self.variable.name} by {self.expr}"
