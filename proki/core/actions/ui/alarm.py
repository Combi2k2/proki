"""{"alarm": {"name": "bedtime", "on": true}}: alarm `bedtime` rings (true) until it's turned
off (false), in the UI (core/ui.py). Each alarm by its own name, so turning one off leaves
the others."""

from __future__ import annotations

from proki.core.actions.base import Action
from proki.core.ui import Ui
from proki.errors import ActionError


class Alarm(Action):
    def __init__(self, name: str, on: bool):
        if not isinstance(name, str) or not name:
            raise ActionError(f"alarm: name is the alarm's name ({name!r})")
        if not isinstance(on, bool):
            raise ActionError(f"alarm {name!r}: on is true (ring) or false (stop) ({on!r})")
        self.name, self.on = name, on

    def apply(self) -> None:
        Ui.alarm(self.name, self.on)

    def __repr__(self) -> str:
        return f"alarm {self.name} {'on' if self.on else 'off'}"
