"""Routine reminders in the running app (rules in core/reminders.py): "around 12:30
is usually time for: a meal" → Going now / Later / Skip today. Outside sessions only.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from proki.legacy.flows.base import Flow, FlowContext
from proki.legacy.core.reminders import ReminderParams, RoutineReminders, Slot, routine_slots
from proki.legacy.core.routines import ACTIVITY_LABEL
from proki.legacy.metrics.day import day_bounds
from proki.legacy.core.store import Store
from proki.legacy.ui.popup import Popup


class RemindersFlow(Flow):
    def __init__(self, store: Store, popup: Popup, day_starts: time, params: ReminderParams = ReminderParams()):
        self.store = store
        self.popup = popup
        self.day_starts = day_starts
        self.reminders = RoutineReminders(params)
        self.params = params
        self._slots: tuple[datetime, list[Slot]] | None = None  # recomputed hourly

    def slots(self, now: datetime) -> list[Slot]:
        if self._slots is None or now - self._slots[0] >= timedelta(hours=1):
            absences = [(start, end, activity) for start, end, activity, _ in self.store.absences()]
            self._slots = (now, routine_slots(absences, self.day_starts, self.params))
        return self._slots[1]

    def step(self, now: datetime, active: bool, in_session: bool) -> None:
        if not active or in_session or self.popup.isVisible():
            return
        slots = self.slots(now)
        if not slots:
            return
        _, day_start, _ = day_bounds(now, self.day_starts)
        today = [(s, e, a) for s, e, a, _ in self.store.absences() if e >= day_start]
        slot = self.reminders.step(now, slots, today, self.day_starts)
        if slot is None:
            return
        label = ACTIVITY_LABEL.get(slot.activity, slot.activity).lower()
        self.popup.ask(
            f"Around {slot.peak:%H:%M} is usually time for {label}. Time for it now?",
            lambda a: self.reminders.settle(slot, now, self.day_starts) if a in ("going", "skip") else None,
            [("Going now", "going"), ("Later", "later"), ("Skip today", "skip")],
        )

    name = "reminders"

    def tick(self, ctx: FlowContext) -> None:
        self.step(ctx.now, ctx.active, in_session=ctx.in_session)

