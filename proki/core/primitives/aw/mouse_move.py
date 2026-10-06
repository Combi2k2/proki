"""`mouse_move`: mouse movement per minute, in pixels."""

from __future__ import annotations

from proki.core.primitives.aw.base import InputRate
from proki.core.primitives.base import Primitive


class MouseMove(InputRate, Primitive):
    def count(self, data: dict) -> float:
        return abs(data.get("deltaX", 0)) + abs(data.get("deltaY", 0))
