"""The morning start in the running app: today's work, the routine timer, "finished
your routine?" when back early, the alarm at the deadline, and the first session.
Rules live in core/morning.py."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

from proki.legacy.flows.base import Flow, FlowContext
from proki.legacy.core.morning import Action, MorningState
from proki.legacy.core.store import Store
from proki.legacy.ui.popup import Popup
from proki.legacy.ui.sound import Alarm

LATE = timedelta(hours=2)  # first activity longer ago than this (e.g. proki started later): not a morning anymore
ROUTINE_OPTIONS = [("15 min", "15"), ("30 min", "30"), ("45 min", "45"), ("60 min", "60"),
                   ("Start now", "now"), ("Heading out today", "out")]


class MorningFlow(Flow):
    def __init__(
        self,
        store: Store,
        popup: Popup,
        alarm: Alarm,
        today: Callable[[datetime], object],
        first_activity: Callable[[datetime], datetime | None],
        todays_work: Callable[[datetime], str],
        request_session: Callable[[], None],
    ):
        self.store = store
        self.popup = popup
        self.alarm = alarm
        self.today = today
        self.first_activity = first_activity
        self.todays_work = todays_work
        self.request_session = request_session
        self.day = None
        self.flow = MorningState()

    def step(self, now: datetime, active: bool, in_session: bool) -> None:
        day = self.today(now)
        if day != self.day:  # a new day: a fresh morning, unless it was already handled
            self.day, self.flow = day, MorningState()
            first = self.first_activity(now)
            if self.store.get_state(f"morning:{day}") or (first and now - first > LATE):
                self.flow.finish()
        action = self.flow.step(now, active, in_session)
        if action is Action.GREET:
            self._mark_done()  # greet once per day, even if proki restarts
            self.popup.ask(
                f"Good morning. {self.todays_work(now)}\n\nFirst, your morning routine: how long do you need?",
                self._routine_answer, ROUTINE_OPTIONS,
            )
        elif action is Action.CHECK:
            self.popup.ask("Finished your morning routine?", self._check_answer,
                           [("Finished", "finished"), ("Not yet", "not_yet")])
        elif action is Action.ALARM:
            self.alarm.start()
            self.popup.ask(
                "Morning routine time is over. Time to start your deep work.",
                self._alarm_answer, [("Start session", "start"), ("Heading out today", "out")],
            )
        elif action is Action.SILENCE:
            self.alarm.stop()

    def _routine_answer(self, answer: str) -> None:
        now = datetime.now(timezone.utc)
        if answer == "now":
            self.flow.finish()
            self.request_session()
        elif answer == "out":
            self.flow.finish()
        else:
            self.flow.start_routine(now, int(answer))

    def _check_answer(self, answer: str) -> None:
        if answer == "not_yet":
            self.flow.not_yet()
            return
        self.popup.ask("Ready to start working?", self._ready_answer, [("Yes, start a session", "yes"), ("Not yet", "no")])

    def _ready_answer(self, answer: str) -> None:
        if answer == "yes":
            self.flow.finish()
            self.request_session()
        else:
            self.flow.finished_not_working()  # the alarm comes at the routine's deadline

    def _alarm_answer(self, answer: str) -> None:
        self.alarm.stop()
        self.flow.finish()
        if answer == "start":
            self.request_session()

    def _mark_done(self) -> None:
        self.store.set_state(f"morning:{self.day}", datetime.now(timezone.utc).isoformat())

    name = "morning"

    def tick(self, ctx: FlowContext) -> None:
        self.step(ctx.now, ctx.active, in_session=ctx.in_session)

