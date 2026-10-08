"""{"set": {"name": variable, "expr": expr}}: the variable to the expression's value."""

from __future__ import annotations

from typing import Any

from proki.core.actions.base import Action
from proki.core.actions.var.base import Update


class Set(Update, Action):
    """Set the variable to the expression's value, worked out on the spot (null: unknown)."""

    def change(self, value: Any) -> None:
        self.variable.set(value)
