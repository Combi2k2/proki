"""The sprint in the running app (core/sprint.py): the next task against its own
estimate, and "time's up" at the end."""

from __future__ import annotations

from typing import Callable

from proki.legacy.flows.base import Flow
from proki.legacy.core.backlog import Task
from proki.legacy.core.sprint import SprintParams
from proki.legacy.ui.popup import Popup


class SprintFlow(Flow):
    def __init__(self, popup: Popup, start_sprint: Callable[[Task | None, str, int], None],
                 next_task: Callable[[], Task | None], new_task: Callable[[], None],
                 params: SprintParams = SprintParams()):
        self.new_task = new_task
        self.popup = popup
        self.start_sprint = start_sprint  # (task, title, minutes)
        self.next_task = next_task
        self.params = params

    def start(self) -> None:
        task = self.next_task()
        if task is None:
            self.popup.ask("Nothing in your task list to sprint on. Add a task first?",
                           lambda a: self.new_task() if a == "add" else None, [("Add a task", "add"), ("Not now", "no")])
            return
        self.start_sprint(task, task.title, task.estimate)  # the deadline is your own estimate

    def times_up(self, title: str, on_answer: Callable[[str], None]) -> None:
        self.popup.ask(f"Time's up: “{title}”. Done?", on_answer,
                       [("Done", "done"), (f"{self.params.extension} more minutes", "more"), ("Stop", "stop")])

    name = "sprint"

