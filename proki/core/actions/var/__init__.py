"""A variable, by an expression's value when applied (base.py: what they share): set, add, sub."""

from proki.core.actions.var.add import Add
from proki.core.actions.var.set import Set
from proki.core.actions.var.sub import Sub

__all__ = ["Add", "Set", "Sub"]
