"""{"add": {"name": variable, "expr": expr}}: add the expression's value to the variable."""

from __future__ import annotations

from typing import Any

from proki.core.actions.base import Action
from proki.core.actions.var.base import Update


class Add(Update, Action):
    """Add the expression's value to the variable, worked out on the spot (an unknown value
    changes nothing, and an unknown variable stays unknown)."""

    def change(self, value: Any) -> None:
        self.variable.add(value)
