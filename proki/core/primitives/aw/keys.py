"""`keys_pressed`: key presses per minute (the watcher counts down and up: its `presses` / 2)."""

from __future__ import annotations

from proki.core.primitives.aw.base import InputRate
from proki.core.primitives.base import Primitive


class Keys(InputRate, Primitive):
    _typed = "number"
    name   = "keys_pressed"
    desc   = "keys pressed per minute"

    def count(self, data: dict) -> float:
        return data.get("presses", 0) / 2
