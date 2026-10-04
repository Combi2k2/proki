"""The rhythmic deep-work block: the same time every day, so it becomes a habit.

Each day's block comes from the default rhythm in the settings (a plan stored for
that day can move its start time). `BlockReminders` decides when to remind the
user that the block has started, with "in 10 minutes" and "skip today".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


@dataclass(frozen=True)
class RhythmParams:
    days: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri")
    start: time = time(9, 0)
    minutes: int = 90
    planning_time: time = time(21, 30)  # when to ask "anything new to take care of?"
    kept_deep_minutes: int = 25  # a block counts as kept with this much deep work in it


@dataclass(frozen=True)
class Plan:
    """A different block start for one day."""

    day: date
    block_start: time


@dataclass(frozen=True)
class Block:
    day: date
    start: datetime
    end: datetime


def block_for(day: date, params: RhythmParams, plan: Plan | None, tz) -> Block | None:
    """The day's block: the rhythm's time, or the plan's (None on days off without a plan)."""
    if plan is None and WEEKDAYS[day.weekday()] not in params.days:
        return None
    start = datetime.combine(day, plan.block_start if plan else params.start, tz)
    return Block(day=day, start=start, end=start + timedelta(minutes=params.minutes))


@dataclass
class BlockReminders:
    """Whether the "your block has started" reminder is due. One instance per day's block."""

    block: Block
    snoozed_until: datetime | None = None
    shown: bool = False
    skipped: bool = False

    def due(self, now: datetime, in_session: bool) -> bool:
        if in_session or self.skipped or self.shown or now < self.block.start or now >= self.block.end:
            return False
        return self.snoozed_until is None or now >= self.snoozed_until

    def snooze(self, now: datetime, minutes: int = 10) -> None:
        self.shown = False
        self.snoozed_until = now + timedelta(minutes=minutes)

    def skip(self) -> None:
        self.skipped = True
