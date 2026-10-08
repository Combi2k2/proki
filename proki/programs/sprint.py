"""The sprint (the legacy sprint flow's) (core/sprint.py): the next task against its own
estimate, and "time's up" at the end."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from proki.core.ui import Ui
from proki.legacy.core.sprint import SprintParams
from proki.programs.base import Ritual, program


class Sprint(Ritual):
    def __init__(self, params: SprintParams = SprintParams()):
        super().__init__("sprint")
        self.params = params

    def start(self) -> None:
        task = program("plan").next_task(datetime.now(timezone.utc))[1]
        if task is None:
            Ui.ask("Nothing in your task list to sprint on. Add a task first?",
                           lambda a: program("plan").new_task() if a == "add" else None, [("Add a task", "add"), ("Not now", "no")])
            return
        program("session").start_sprint(task, task.title, task.estimate)  # the deadline is your own estimate

    def times_up(self, title: str, on_answer: Callable[[str], None]) -> None:
        Ui.ask(f"Time's up: “{title}”. Done?", on_answer,
                       [("Done", "done"), (f"{self.params.extension} more minutes", "more"), ("Stop", "stop")])


