"""Productive meditation in the running app: suggest a thinking walk after a good
session (or start one from the tray), ask for the problem and the length, and
when the user is back, what they figured out (kept as a note). Rules live in
core/meditation.py.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Callable

from proki.legacy.flows.base import Flow
from proki.legacy.core.backlog import Task
from proki.legacy.core.meditation import MeditationParams, should_suggest, walk_task
from proki.legacy.core.store import Store
from proki.legacy.ui.popup import Popup


class MeditationFlow(Flow):
    def __init__(self, store: Store, popup: Popup, start_walk: Callable[[Task], None],
                 current_task: Callable[[], Task | None], params: MeditationParams = MeditationParams(),
                 rng: random.Random | None = None):
        self.store = store
        self.popup = popup
        self.start_walk = start_walk  # starts a session on the walk
        self.current_task = current_task  # to suggest the problem
        self.params = params
        self.rng = rng or random.Random()

    def after_session(self, deep_minutes: int) -> None:
        """A session just ended: sometimes suggest a thinking walk."""
        if self.popup.isVisible() or not should_suggest(deep_minutes, self.params, self.rng):
            return
        self.popup.ask(
            "Good session. Take a walk and think through one problem? (It counts as deep work.)",
            lambda a: self.start() if a == "walk" else None,
            [("Thinking walk", "walk"), ("Not now", "no")],
        )

    def start(self, problem_hint: str | None = None) -> None:
        task = self.current_task()
        self.popup.ask_text(
            "Which one problem will you think through? Make it specific: the next question to answer.",
            self._problem, placeholder="e.g. how should the quota handle sick days?",
            skip_label="Cancel", text=problem_hint or (task.title if task else ""),
        )

    def _problem(self, problem: str | None) -> None:
        if problem is None:
            return
        self.popup.ask(
            f"How long a walk for “{problem}”?",
            lambda a: self.start_walk(walk_task(problem, int(a))) if a != "cancel" else None,
            [(f"{m} min", str(m)) for m in self.params.lengths] + [("Cancel", "cancel")],
        )

    def back(self, walk: Task, minutes: int) -> None:
        """Back from the walk: what came out of it?"""
        self.popup.ask_text(
            f"Welcome back ({minutes} min of thinking). What did you figure out about “{walk.title}”?",
            lambda text: self._outcome(walk, text), placeholder="the answer, the next step, a new question…",
            skip_label="Nothing yet",
        )

    def _outcome(self, walk: Task, text: str | None) -> None:
        if text:
            self.store.add_note(f"Thinking walk, “{walk.title}”: {text}", None, datetime.now(timezone.utc))

    name = "thinking walk"

