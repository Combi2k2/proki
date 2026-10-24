"""choices(x): the values x's type allows, in its order (of a list: its items').

    choices(work.group.tags)          every tag a group can have

Empty if its type names none.
"""

from __future__ import annotations

from typing import Any

from proki.core.ops.base import Operand
from proki.core.ops.lift import Lift
from proki.types import itemof, listof, schema


class Choices(Lift):
    USAGE = "choices(x)"
    ABOUT = "the values x's type allows: choices(work.group.tags), every tag a group can have"

    def __init__(self, x: Operand):
        super().__init__(None, x, unknown=True, type=lambda of: listof(one(of(self.inputs[0]))))

    def compute(self) -> Any:
        return list(schema(one(self.inputs[0].type)).get("enum", []))


def one(type: Any) -> Any:
    """The type of one of x's values: a list's items', else its own."""
    return itemof(type) if schema(type).get("type") == "array" else type
