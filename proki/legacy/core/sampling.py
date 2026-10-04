"""When to ask "how focused are you right now?" (experience sampling).

Each day gets `per_day` random times inside working hours, at least `min_gap`
apart. A planned time only fires while the user is at the computer; if they're
away it waits (up to `patience`), otherwise that sample is dropped. The ratings
are ground truth for calibrating the focus score to this person.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True)
class SamplingParams:
    per_day: int = 5
    start: time = time(9, 0)
    end: time = time(18, 0)
    min_gap: timedelta = timedelta(minutes=45)
    patience: timedelta = timedelta(minutes=30)  # how long a sample may wait for the user to come back


def plan_day(day: date, params: SamplingParams, rng: random.Random, tz) -> list[datetime]:
    """Random times on `day` within working hours, at least `min_gap` apart, sorted."""
    start = datetime.combine(day, params.start, tz)
    end = datetime.combine(day, params.end, tz)
    span = (end - start).total_seconds()
    for _ in range(200):  # rejection sampling; fine for a handful of samples a day
        times = sorted(start + timedelta(seconds=rng.uniform(0, span)) for _ in range(params.per_day))
        if all(b - a >= params.min_gap for a, b in zip(times, times[1:])):
            return times
    # too many samples for the gap: spread them evenly instead
    step = span / max(params.per_day, 1)
    return [start + timedelta(seconds=step * (i + 0.5)) for i in range(params.per_day)]


class SamplingSchedule:
    def __init__(self, params: SamplingParams, rng: random.Random | None = None):
        self.params = params
        self.rng = rng or random.Random()
        self.day: date | None = None
        self.pending: list[datetime] = []

    def due(self, now: datetime, away: bool) -> bool:
        """True when a sample should be asked now. Consumes that sample."""
        local = now.astimezone()
        if local.date() != self.day:
            self.day = local.date()
            self.pending = [t for t in plan_day(self.day, self.params, self.rng, local.tzinfo) if t > local]
        # drop samples that waited too long for the user to come back
        self.pending = [t for t in self.pending if local - t <= self.params.patience]
        if away or not self.pending or self.pending[0] > local:
            return False
        self.pending.pop(0)
        return True
