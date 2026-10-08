"""{"sub": {"name": variable, "expr": expr}}: subtract the expression's value from the variable."""

from __future__ import annotations

from typing import Any

from proki.core.actions.base import Action
from proki.core.actions.var.base import Update


class Sub(Update, Action):
    """Subtract the expression's value from the variable, worked out on the spot (an
    unknown value changes nothing, and an unknown variable stays unknown)."""

    def change(self, value: Any) -> None:
        self.variable.sub(value)
