"""{"lock": {}}: lock the screen (the UI does it, core/ui.py)."""

from __future__ import annotations

from proki.core.actions.base import Action
from proki.core.ui import Ui


class Lock(Action):
    def __init__(self):
        pass

    def apply(self) -> None:
        Ui.lock()

    def __repr__(self) -> str:
        return "lock"
