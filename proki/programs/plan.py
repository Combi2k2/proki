"""The plan: which task to work on, handed over when a session starts (the legacy tasks
flow's; the backlog's rules are in legacy/core/backlog.py).

A program written in code, named "plan". Its states:
- idle: no session;
- offering: a session started (`start_session`), the next task offered (Start / Start
  offline / Other group / Done);
- working: the session's task is the user's (or there's none: the offer went unanswered),
  until the session ends (`end_session`).

For the config it keeps two variables: `tasks_open` (how many tasks can be worked on
now) and `task` (the current task's title, or null). The tasks are the app's
(`TaskStore`: proki.db's backlog); adding one is the UI's (`new_task`), and so is the task
window (`refresh` after a change).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any, Protocol

from proki.core.ui import Ui
from proki.legacy.core import backlog
from proki.legacy.core.backlog import Group, Task
from proki.programs.base import Ritual, variable

START, OFFLINE, OTHER, DONE = "start", "offline", "other", "done"


class TaskStore(Protocol):
    def tasks(self) -> list[Task]: ...
    def groups(self) -> list[Group]: ...
    def set_task_status(self, task_id: int, status: str, at: datetime) -> None: ...
    def update_task(self, task_id: int, **fields) -> None: ...
    def set_running_session_group(self, group_id: int | None) -> None: ...
    def get_state(self, key: str) -> str | None: ...
    def set_state(self, key: str, value: str) -> None: ...


class Plan(Ritual):
    def __init__(self, store: TaskStore, new_task: Callable[..., None] = lambda **kwargs: None,
                 refresh: Callable[[], None] = lambda: None,
                 today: Callable[[datetime], date] = lambda now: now.astimezone().date()):
        super().__init__("plan", ("idle", "offering", "working"))
        self.store = store
        self.new_task = new_task  # opens the task form (the UI's): new_task(then=..., title=...)
        self.refresh = refresh  # the task window, after a change
        self.today = today
        self.group: Group | None = None  # the goal group this session works on
        self.current_task: Any = self._saved_current_task()  # a Task, or a walk (core/meditation.py)
        self.skipped: set[int] = set()  # groups the user passed on, this session
        variable("tasks_open", 0)
        variable("task")

    def step(self, now: datetime) -> None:
        variable("tasks_open").set(len(backlog.workable(self.store.tasks())))

    # --- sessions -------------------------------------------------------------------------

    def has_work(self) -> bool:
        return bool(backlog.workable(self.store.tasks()))

    def request_session(self, start_session: Callable[[], None]) -> None:
        """Start a session; with an empty task list, offer to add a task first."""
        if self.has_work():
            start_session()
            return
        Ui.ask("Your task list is empty. Add what needs doing first?",
               lambda a: self.new_task(then=start_session) if a == "add" else start_session(),
               [("Add a task", "add"), ("Start anyway", "start")])

    def start_session(self) -> None:
        """At session start: pick the most urgent goal group and hand over its first task."""
        self.skipped, self.group = set(), None
        self.use(None)
        self.offer_task()

    def end_session(self) -> None:
        self.current, self.group = "idle", None
        self.use(None)

    def use(self, task: Any) -> None:
        """The session's task (a sprint's, a walk) without asking."""
        self.current_task = task
        if task is not None and self.current == "idle":
            self.current = "working"
        variable("task").set(task.title if task else None)
        self.store.set_state("session_task", str(task.id) if task is not None else "")  # survives a restart

    def _saved_current_task(self) -> Task | None:
        saved = self.store.get_state("session_task")
        if not saved or not saved.lstrip("-").isdigit():
            return None
        return next((t for t in self.store.tasks() if t.id == int(saved) and t.status == "open"), None)

    # --- handing over a task ----------------------------------------------------------------

    def next_task(self, now: datetime) -> tuple[Group | None, Task | None]:
        tasks = self.store.tasks()
        group = self.group or backlog.pick_group(self.store.groups(), tasks, now, self.skipped)
        if group is None:  # tasks without a group, if that's all there is
            return None, backlog.next_task(tasks, None)
        return group, backlog.next_task(tasks, group.id)

    def offer_task(self) -> None:
        now = self._now()
        group, task = self.next_task(now)
        if task is None and self.group is not None:
            finished = self.group.name
            self.skipped.add(self.group.id)
            self.group = None
            group, task = self.next_task(now)
            if task is not None:
                self._offer(group, task, f"“{finished}” is all done. Next up: “{group.name if group else 'other tasks'}”.")
                return
        if task is None:
            self.current = "working"  # a session without a task
            Ui.ask("Nothing left to work on in your task list. Add a new task?",
                   lambda a: self.new_task() if a == "add" else None, [("Add a task", "add"), ("Not now", "no")])
            return
        self._offer(group, task, "")

    def _offer(self, group: Group | None, task: Task, intro: str) -> None:
        self.group = group
        where = f"This session: {group.name} ({backlog.due_text(task.deadline, self.today(self._now()))})\n" if group else ""
        text = f"{intro + chr(10) if intro else ''}{where}Next: {task.title}  (~{backlog.minutes_text(task.estimate)})"
        if task.offline or backlog.ask_if_offline(task):
            # offline first: the user confirms (or overrules) jev's or their earlier answer
            note = "You do this one away from the computer." if task.offline else "This looks like it can be done away from the computer."
            text += f"\n{note} Away time then counts as deep work."
            starts = [("Start offline", OFFLINE), ("At the computer", START)]
        else:
            starts = [("Start", START), ("Start offline", OFFLINE)]
        self.current = "offering"
        Ui.ask(text, lambda a: self._on_offer(a, task), starts + [("Other group", OTHER), ("Done", DONE)])

    def _on_offer(self, answer: str, task: Task) -> None:
        if self.current != "offering":
            return  # the session ended meanwhile
        if answer in (START, OFFLINE):
            offline = answer == OFFLINE
            if task.offline != offline:
                self.store.update_task(task.id, offline=int(offline))
            self.current = "working"
            self.use(next((t for t in self.store.tasks() if t.id == task.id), task))
            self.store.set_running_session_group(task.group_id)  # for the weekly review: time per goal
        elif answer == DONE:
            self._set_status(task, "done")
            self.offer_task()
        elif answer == OTHER:
            if self.group is not None:
                self.skipped.add(self.group.id)
            self.group = None
            self.offer_task()

    def task_done(self) -> None:
        """The tray: the current task is finished; hand over the next one from the same group."""
        task = self.current_task or self.next_task(self._now())[1]
        self.use(None)
        if task:
            self._set_status(task, "done")
        self.offer_task()

    def _set_status(self, task: Task, status: str) -> None:
        self.store.set_task_status(task.id, status, self._now())
        self.refresh()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
