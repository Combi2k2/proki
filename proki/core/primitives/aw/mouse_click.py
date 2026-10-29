"""`mouse_click`: mouse clicks per minute."""

from __future__ import annotations

from proki.core.primitives.aw.base import InputRate
from proki.core.primitives.base import Primitive


class MouseClick(InputRate, Primitive):
    _typed = "number"
    desc   = "mouse clicks per minute"

    def count(self, data: dict) -> float:
        return data.get("clicks", 0)
