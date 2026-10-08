"""Productive meditation (the legacy meditation flow's): suggest a thinking walk after a good
session (or start one from the tray), ask for the problem and the length, and
when the user is back, what they figured out (kept as a note). Rules live in
core/meditation.py.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

from proki.core.ui import Ui
from proki.legacy.core.meditation import MeditationParams, should_suggest, walk_task
from proki.legacy.core.store import Store
from proki.legacy.core.backlog import Task
from proki.programs.base import Ritual, program


class Meditation(Ritual):
    def __init__(self, store: Store, params: MeditationParams = MeditationParams(), rng: random.Random | None = None):
        super().__init__("meditation")
        self.store = store
        self.params = params
        self.rng = rng or random.Random()

    def after_session(self, deep_minutes: int) -> None:
        """A session just ended: sometimes suggest a thinking walk."""
        if Ui.busy() or not should_suggest(deep_minutes, self.params, self.rng):
            return
        Ui.ask(
            "Good session. Take a walk and think through one problem? (It counts as deep work.)",
            lambda a: self.start() if a == "walk" else None,
            [("Thinking walk", "walk"), ("Not now", "no")],
        )

    def start(self, problem_hint: str | None = None) -> None:
        task = program("plan").next_task(datetime.now(timezone.utc))[1]  # to suggest the problem
        Ui.ask_text(
            "Which one problem will you think through? Make it specific: the next question to answer.",
            self._problem, placeholder="e.g. how should the quota handle sick days?",
            skip_label="Cancel", text=problem_hint or (task.title if task else ""),
        )

    def _problem(self, problem: str | None) -> None:
        if problem is None:
            return
        Ui.ask(
            f"How long a walk for “{problem}”?",
            lambda a: program("session").start_walk(walk_task(problem, int(a))) if a != "cancel" else None,
            [(f"{m} min", str(m)) for m in self.params.lengths] + [("Cancel", "cancel")],
        )

    def back(self, walk: Task, minutes: int) -> None:
        """Back from the walk: what came out of it?"""
        Ui.ask_text(
            f"Welcome back ({minutes} min of thinking). What did you figure out about “{walk.title}”?",
            lambda text: self._outcome(walk, text), placeholder="the answer, the next step, a new question…",
            skip_label="Nothing yet",
        )

    def _outcome(self, walk: Task, text: str | None) -> None:
        if text:
            self.store.add_note(f"Thinking walk, “{walk.title}”: {text}", None, datetime.now(timezone.utc))


