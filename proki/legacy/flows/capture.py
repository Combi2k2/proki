"""Capture in the running app: "anything worth noting?" on shallow work and
distractions, notes that become tasks, and "finished?" for tasks from a tab or
window (with closing it). Rules live in core/capture.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from proki import platforms
from proki.legacy.flows.base import Flow, FlowContext
from proki.legacy.core.capture import CaptureParams, CaptureWatch, FollowUps, Source
from proki.legacy.core.events import Category, Segment
from proki.legacy.core.store import Store
from proki.legacy.flows.tasks import TasksFlow
from proki.legacy.ui.background import Background
from proki.legacy.ui.popup import Popup

TODO_LIKELY = 0.5  # openjev at least this sure a note is a to-do → offer to add it as a task


class CaptureFlow(Flow):
    def __init__(self, store: Store, popup: Popup, tasks: TasksFlow,
                 is_todo: Callable[[str], float | None] | None, params: CaptureParams = CaptureParams()):
        self.store = store
        self.popup = popup
        self.tasks = tasks
        self.is_todo = is_todo  # openjev: how likely a note is a to-do; may be slow
        self.watch = CaptureWatch(params)
        self.follow_ups = FollowUps(params)
        self.sources: list[tuple[int, Source]] = []  # open tasks from a tab/window, refreshed every tick
        self.background = Background()

    def refresh(self) -> None:
        self.sources = self.store.task_sources()

    def step(self, now: datetime, segment: Segment | None, category: Category | None, in_session: bool) -> None:
        """Every poll (a few seconds)."""
        source = self.watch.step(now, segment, category, in_session)
        if in_session or self.popup.isVisible() or self.tasks.form.isVisible():
            return
        if source is not None:
            self._ask_note(source)
            return
        task_id = self.follow_ups.step(now, segment, self.sources)
        if task_id is not None:
            self._ask_finished(task_id)

    # --- notes ---------------------------------------------------------------------------

    def _ask_note(self, source: Source) -> None:
        if source.category is Category.DISTRACTION:
            message = f"You've been on {source.key} for a while. Anything interesting worth noting?"
        else:
            message = f"You're on {source.key}. Anything worth noting, or anything to do?"
        self.popup.ask_text(message, lambda text: self._noted(text, source),
                            placeholder="an idea, something to do…", skip_label="Nothing")

    def _noted(self, text: str | None, source: Source) -> None:
        if text is None:
            return
        note_id = self.store.add_note(text, source, datetime.now(timezone.utc))
        if self.is_todo:
            self.background.run(lambda: self.is_todo(text), lambda p: self._checked(note_id, text, source, p))

    def _checked(self, note_id: int, text: str, source: Source, probability: float | None) -> None:
        if probability is None or probability < TODO_LIKELY or self.popup.isVisible():
            return
        self.popup.ask(
            f"“{text}” sounds like something to do. Add it to your tasks?",
            lambda a: self._add_task(note_id, text, source) if a == "add" else None,
            [("Add task", "add"), ("Just a note", "note")],
        )

    def _add_task(self, note_id: int, text: str, source: Source) -> None:
        def added(task_id: int) -> None:
            self.store.link_note(note_id, task_id)
            self.refresh()

        self.tasks.new_task(title=text, source=source, on_added=added)

    # --- "finished?" -------------------------------------------------------------------------

    def _ask_finished(self, task_id: int) -> None:
        task = next((t for t in self.store.tasks() if t.id == task_id), None)
        source = dict(self.sources).get(task_id)
        if task is None or source is None:
            return
        thing = "tab" if source.url else "window"
        where = source.title or source.url or source.app
        self.popup.ask(
            f"Did you finish “{task.title}”?\n(from: {where})",
            lambda a: self._finished(a, task_id, source),
            [(f"Done, close the {thing}", "done_close"), ("Done", "done"),
             (f"Another day, close the {thing}", "later_close"), ("Not yet", "not_yet")],
        )

    def _finished(self, answer: str, task_id: int, source: Source) -> None:
        now = datetime.now(timezone.utc)
        if answer == "not_yet":
            self.follow_ups.not_yet(task_id, now)
            return
        if answer.startswith("done"):
            self.store.set_task_status(task_id, "done", now)
        else:
            # stays in the backlog; the link is kept on the task, so closing loses nothing.
            # Not asked again about this tab/window.
            self.store.update_task(task_id, source_app=None)
        if answer.endswith("close"):
            closed = (platforms.current().close_tab(source.app, source.url) if source.url
                      else platforms.current().close_window(source.app, source.title))
            if not closed:
                self.popup.ask(f"Couldn't close it ({source.app}); please close it yourself.", lambda _: None, [("OK", "ok")])
        self.refresh()
        self.tasks.refresh()

    name = "capture"

    def tick(self, ctx: FlowContext) -> None:
        self.refresh()

    def poll(self, ctx: FlowContext) -> None:
        # after the workday is shut down, no more work questions
        self.step(ctx.now, ctx.current, ctx.category, in_session=ctx.in_session or bool(ctx.state.get("shutdown_done")))

