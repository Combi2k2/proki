"""Tasks in the running app: the task window, new tasks, breaking them down, the
evening "anything new?" prompt, and handing over one group's tasks during a session.

Logic lives in core/backlog.py; this module decides which window to show and
stores what the user entered.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Callable

from proki.legacy.flows.base import Flow
from proki.legacy.core import backlog
from proki.legacy.core.backlog import Assessment, Group, Task
from proki.legacy.metrics.day import day_bounds
from proki.legacy.core.store import Store
from proki.legacy.ui.breakdown import BreakdownDialog
from proki.legacy.ui.popup import Popup
from proki.legacy.ui.task_board import TaskBoard
from proki.legacy.ui.task_form import TaskForm


class TasksFlow(Flow):
    def __init__(
        self,
        store: Store,
        popup: Popup,
        today: Callable[[datetime], date],
        day_starts: time,
        deep_minutes_today: Callable[[datetime], int],
        assess: Callable[[str], Assessment | None] | None,
        suggest_group: Callable[[str, list[str]], str | None] | None,
        helper,  # core.ai.TaskHelper or None: step suggestions
    ):
        self.store = store
        self.popup = popup
        self.today = today
        self.day_starts = day_starts
        self.deep_minutes_today = deep_minutes_today
        self.helper = helper
        self.form = TaskForm(assess, suggest_group)
        self.breakdown_dialog = BreakdownDialog()
        self.board = TaskBoard(
            on_new=lambda: self.new_task(),
            on_edit=self.edit_task,
            on_breakdown=lambda t: self.breakdown(t, "too_long" if t.estimate > backlog.SESSION_MINUTES else "vague"),
            on_done=lambda t: self._set_status(t, "done"),
            on_remove=lambda t: self._set_status(t, "dropped"),
            on_priority=self._set_priority,
        )
        self.session_group: Group | None = None  # the goal group this session works on
        self.current_task: Task | None = self._saved_current_task()  # the task started in this session
        self.skipped_groups: set[int] = set()
        self._after_save: Callable[[], None] | None = None
        self._source = None  # core.capture.Source of the task being added from a note
        self._on_added: Callable[[int], None] | None = None

    # --- the task window and forms -----------------------------------------------------

    def open_board(self) -> None:
        self.refresh()
        self.board.open()

    def refresh(self) -> None:
        now = datetime.now(timezone.utc)
        _, start, end = day_bounds(now, self.day_starts)
        self.board.refresh(self.store.groups(), self.store.tasks(), self.today(now), now,
                           self.store.tasks_done_between(start, end), self.deep_minutes_today(now))

    def new_task(self, then: Callable[[], None] | None = None, title: str = "", source=None,
                 on_added: Callable[[int], None] | None = None) -> None:
        """`source`: the tab/window a task noted there came from (for "finished?" later)."""
        self._after_save, self._source, self._on_added = then, source, on_added
        now = datetime.now(timezone.utc)
        self.form.open(self._group_priorities(), backlog.default_deadline(self.today(now)), self._saved, title=title)

    def edit_task(self, task: Task) -> None:
        self._after_save, self._source, self._on_added = None, None, None
        names = {g.id: g.name for g in self.store.groups()}
        default = backlog.default_deadline(self.today(datetime.now(timezone.utc)))
        self.form.open(self._group_priorities(), default, self._saved, task=task, group_name=names.get(task.group_id))

    def _group_priorities(self) -> dict[str, str]:
        return {g.name: g.priority for g in self.store.groups()}

    def _saved(self, fields: dict, assessment: Assessment | None, reason: str | None) -> None:
        now = datetime.now(timezone.utc)
        group_id = None
        if fields["group"]:
            group_id = self.store.add_group(fields["group"], fields["priority"], now)
            self.store.set_group_priority(group_id, fields["priority"])
        editing: Task | None = fields["task"]
        if editing:
            self.store.update_task(editing.id, group_id=group_id, title=fields["title"], description=fields["description"],
                                   deadline=fields["deadline"], estimate=fields["estimate"])
            task_id = editing.id
        else:
            task_id = self.store.add_task(group_id, fields["title"], fields["description"], fields["deadline"],
                                          fields["estimate"], now, assessment=assessment)
            if self._source is not None:
                self.store.update_task(task_id, source_app=self._source.app, source_title=self._source.title,
                                       source_url=self._source.url)
            if self._on_added:
                self._on_added(task_id)
            self._source = self._on_added = None
        self.refresh()
        task = next(t for t in self.store.tasks() if t.id == task_id)
        if reason:
            self.breakdown(task, reason)
        elif self._after_save:
            then, self._after_save = self._after_save, None
            then()

    def breakdown(self, task: Task, reason: str) -> None:
        suggest = None
        if self.helper:
            suggest = lambda: self.helper.steps(task.title, task.description, task.estimate, reason)
        self.breakdown_dialog.open(task, reason, suggest, self._save_steps)

    def _save_steps(self, task: Task, steps: list[tuple[str, int]]) -> None:
        now = datetime.now(timezone.utc)
        for title, minutes in steps:
            self.store.add_task(task.group_id, title, "", task.deadline, minutes, now, parent_id=task.id)
        self.refresh()
        if self._after_save:
            then, self._after_save = self._after_save, None
            then()

    def _set_status(self, task: Task, status: str) -> None:
        self.store.set_task_status(task.id, status, datetime.now(timezone.utc))
        self.refresh()

    def _set_priority(self, group: Group, priority: str) -> None:
        self.store.set_group_priority(group.id, priority)
        self.refresh()

    # --- the evening prompt ----------------------------------------------------------------

    def ask_anything_new(self) -> None:
        self.popup.ask(
            "Anything new to take care of?",
            lambda a: self.new_task() if a == "add" else None,
            [("Add a task", "add"), ("Nothing new", "no")],
        )

    # --- sessions ----------------------------------------------------------------------------

    def has_work(self) -> bool:
        return bool(backlog.workable(self.store.tasks()))

    def request_session(self, start_session: Callable[[], None]) -> None:
        """Start a session; with an empty task list, offer to add a task first."""
        if self.has_work():
            start_session()
            return
        self.popup.ask(
            "Your task list is empty. Add what needs doing first?",
            lambda a: self.new_task(then=start_session) if a == "add" else start_session(),
            [("Add a task", "add"), ("Start anyway", "start")],
        )

    def start_session(self) -> None:
        """At session start: pick the most urgent goal group and hand over its first task."""
        self.skipped_groups = set()
        self.session_group = None
        self._set_current(None)
        self.offer_task()

    def end_session(self) -> None:
        self.session_group = None
        self._set_current(None)

    def _set_current(self, task: Task | None) -> None:
        self.current_task = task
        self.store.set_state("session_task", str(task.id) if task else "")  # survives a restart

    def _saved_current_task(self) -> Task | None:
        saved = self.store.get_state("session_task")
        if not saved:
            return None
        return next((t for t in self.store.tasks() if t.id == int(saved) and t.status == "open"), None)

    def next_task(self, now: datetime) -> tuple[Group | None, Task | None]:
        tasks = self.store.tasks()
        group = self.session_group or backlog.pick_group(self.store.groups(), tasks, now, self.skipped_groups)
        if group is None:  # tasks without a group, if that's all there is
            loose = backlog.next_task(tasks, None)
            return None, loose
        return group, backlog.next_task(tasks, group.id)

    def offer_task(self) -> None:
        now = datetime.now(timezone.utc)
        group, task = self.next_task(now)
        if task is None and self.session_group is not None:
            finished = self.session_group.name
            self.skipped_groups.add(self.session_group.id)
            self.session_group = None
            group, task = self.next_task(now)
            if task is not None:
                self._offer(group, task, f"“{finished}” is all done. Next up: “{group.name if group else 'other tasks'}”.")
                return
        if task is None:
            self.popup.ask(
                "Nothing left to work on in your task list. Add a new task?",
                lambda a: self.new_task() if a == "add" else None,
                [("Add a task", "add"), ("Not now", "no")],
            )
            return
        self._offer(group, task, "")

    def _offer(self, group: Group | None, task: Task, intro: str) -> None:
        self.session_group = group
        today = self.today(datetime.now(timezone.utc))
        where = f"This session: {group.name} ({backlog.due_text(task.deadline, today)})\n" if group else ""
        text = f"{intro + chr(10) if intro else ''}{where}Next: {task.title}  (~{backlog.minutes_text(task.estimate)})"
        if task.offline or backlog.ask_if_offline(task):
            # offline first: the user confirms (or overrules) openjev's or their earlier answer
            note = "You do this one away from the computer." if task.offline else "This looks like it can be done away from the computer."
            text += f"\n{note} Away time then counts as deep work."
            starts = [("Start offline", "offline"), ("At the computer", "start")]
        else:
            starts = [("Start", "start"), ("Start offline", "offline")]
        self.popup.ask(text, lambda a: self._on_offer(a, task), starts + [("Other group", "other"), ("Done", "done")])

    def _on_offer(self, answer: str, task: Task) -> None:
        if answer in ("start", "offline"):
            offline = answer == "offline"
            if task.offline != offline:
                self.store.update_task(task.id, offline=int(offline))
            self._set_current(next(t for t in self.store.tasks() if t.id == task.id))
            self.store.set_running_session_group(task.group_id)  # for the weekly review: time per goal
        elif answer == "done":
            self._set_status(task, "done")
            self.offer_task()
        elif answer == "other":
            if self.session_group is not None:
                self.skipped_groups.add(self.session_group.id)
            self.session_group = None
            self.offer_task()

    def task_done(self) -> None:
        """Tray: the current task is finished; hand over the next one from the same group."""
        task = self.current_task or self.next_task(datetime.now(timezone.utc))[1]
        self._set_current(None)
        if task:
            self._set_status(task, "done")
        self.offer_task()

    name = "tasks"

