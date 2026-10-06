"""`mouse_scroll`: scrolling per minute, in scroll units."""

from __future__ import annotations

from proki.core.primitives.aw.base import InputRate
from proki.core.primitives.base import Primitive


class MouseScroll(InputRate, Primitive):
    def count(self, data: dict) -> float:
        return abs(data.get("scrollX", 0)) + abs(data.get("scrollY", 0))
