"""{"open": {"view": "task_form"}}: open one of the UI's views (core/ui.py): task_form (a
new task), task_board (the task list)."""

from __future__ import annotations

from proki.core.actions.base import Action
from proki.core.ui import Ui
from proki.errors import ActionError

VIEWS = ("task_form", "task_board")


class Open(Action):
    def __init__(self, view: str):
        if view not in VIEWS:
            raise ActionError(f"open: view is one of {', '.join(VIEWS)} ({view!r})")
        self.view = view

    def apply(self) -> None:
        Ui.open(self.view)

    def __repr__(self) -> str:
        return f"open {self.view}"
