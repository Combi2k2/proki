"""Routine reminders from the user's own typical times (meals, sport, walks, ...).

From the absences the user labelled (core/routines.py), each activity gets its
usual times of day: the peaks of the (smoothed) distribution of its start times,
each with enough days behind it. A meal can have several (breakfast, lunch,
dinner).

Reminders are a rule (core/rule.py), sampled every 15 minutes while nothing that
looks like it has happened yet today: the quantity is the share of past days on
which it had already started by this time of day; threshold 0.5 (even odds when
half the days had started), soft (0.2 → 18%, 0.8 → 82%); never before the
earliest past start.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from proki.legacy.rules.base import Cadence

DAY = 24 * 60


@dataclass(frozen=True)
class ReminderParams:
    min_days: int = 3  # days an activity must have happened around a time to be a routine
    bandwidth: timedelta = timedelta(minutes=30)  # smoothing of the start-time distribution
    window: timedelta = timedelta(minutes=90)  # a slot covers its peak ± this
    min_absence: timedelta = timedelta(minutes=10)  # an absence in the window this long may be it
    check_every: timedelta = timedelta(minutes=15)
    threshold: float = 0.5  # share of past days already started → 50% chance
    softness: float = 0.2
    exclude: tuple[str, ...] = ("sleep", "toilet", "offline_task")  # handled elsewhere, or not worth reminding


@dataclass(frozen=True)
class Slot:
    """One usual time for one activity."""

    activity: str
    peak: time
    starts: tuple[float, ...]  # past start times, minutes after the day starts

    def key(self) -> str:
        return f"{self.activity}@{self.peak:%H:%M}"


def _after(t: datetime, day_starts: time) -> float:
    local = t.astimezone()
    return (local.hour * 60 + local.minute + local.second / 60 - day_starts.hour * 60 - day_starts.minute) % DAY


def _clock(minutes: float, day_starts: time) -> time:
    m = int(round(minutes + day_starts.hour * 60 + day_starts.minute)) % DAY
    return time(m // 60, m % 60)


def _day_of(t: datetime, day_starts: time) -> date:
    local = t.astimezone()
    return local.date() if local.time() >= day_starts else local.date() - timedelta(days=1)


def routine_slots(absences: list[tuple[datetime, datetime, str | None]], day_starts: time,
                  params: ReminderParams = ReminderParams()) -> list[Slot]:
    """Usual times per activity from labelled absences (start, end, activity)."""
    by_activity: dict[str, list[tuple[float, date]]] = {}
    for start, _, activity in absences:
        if activity and activity not in params.exclude:
            by_activity.setdefault(activity, []).append((_after(start, day_starts), _day_of(start, day_starts)))
    band = params.bandwidth.total_seconds() / 60
    window = params.window.total_seconds() / 60
    slots = []
    for activity, points in by_activity.items():
        density = [sum(math.exp(-0.5 * ((m - x) / band) ** 2) for x, _ in points) for m in range(0, DAY, 5)]
        for i, d in enumerate(density):
            neighbours = density[max(i - 1, 0)], density[min(i + 1, len(density) - 1)]
            if d <= 0 or d < max(neighbours) or (i > 0 and d == density[i - 1]):
                continue  # not a peak (for flat tops, only the first point)
            peak = i * 5
            near = [(x, day) for x, day in points if abs(x - peak) <= window]
            if len({day for _, day in near}) >= params.min_days:
                slots.append(Slot(activity, _clock(peak, day_starts), tuple(sorted(x for x, _ in near))))
    return slots


def started_share(slot: Slot, now: datetime, day_starts: time) -> float:
    """Share of past days on which it had started by this time of day (0 before its window)."""
    now_m = _after(now, day_starts)
    return sum(1 for x in slot.starts if x <= now_m) / len(slot.starts)


def done_today(slot: Slot, today: list[tuple[datetime, datetime, str | None]], day_starts: time,
               params: ReminderParams = ReminderParams()) -> bool:
    """Something today that could be it: an absence in the slot's window, labelled as it or not labelled."""
    peak = slot.peak.hour * 60 + slot.peak.minute - day_starts.hour * 60 - day_starts.minute
    window = params.window.total_seconds() / 60
    for start, end, activity in today:
        if end - start >= params.min_absence and abs(_after(start, day_starts) - peak % DAY) <= window:
            if activity in (None, slot.activity):
                return True
    return False


class RoutineReminders:
    """Every `check_every`, samples whether to remind about each routine not done yet today."""

    def __init__(self, params: ReminderParams = ReminderParams(), rng: random.Random | None = None):
        self.params = params
        from proki.legacy.rules.reminder import ReminderRule

        self.rule = ReminderRule(params, rng)
        self.cadence = Cadence(params.check_every)
        self.settled: dict[str, date] = {}  # slot key → day it was reminded / skipped

    def step(self, now: datetime, slots: list[Slot], today: list[tuple[datetime, datetime, str | None]],
             day_starts: time) -> Slot | None:
        if not self.cadence.due(now):
            return None
        day = _day_of(now, day_starts)
        for slot in slots:
            if self.settled.get(slot.key()) == day or done_today(slot, today, day_starts, self.params):
                continue
            if self.rule.decide(self.rule.context(slot, now, day_starts)):
                return slot
        return None

    def settle(self, slot: Slot, now: datetime, day_starts: time) -> None:
        """No more reminders for this slot today (going now, or skipped)."""
        self.settled[slot.key()] = _day_of(now, day_starts)
