"""str(x): x as text, a whole number without its .0.

    'about ' + str(task.estimate) + ' min'      about 40 min, not 40.0

Unknown if x is.
"""

from __future__ import annotations

from typing import Any

from proki.core.ops.base import Operand
from proki.core.ops.lift import Lift


class Str(Lift):
    USAGE = "str(x)"
    ABOUT = "x as text: 40, not 40.0 (to write in a text: 'about ' + str(task.estimate) + ' min')"

    def __init__(self, x: Operand):
        super().__init__(said, x, type="string")


def said(value: Any) -> str:
    """A value as text: a whole number without its .0."""
    return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)
