"""Consistency of session start times: deep work at a similar time every day.

The usual start = the median of each day's first session start over the last two
weeks (days without a session are left out). A day is consistent when its first
session started within ±30 minutes of it. The tray shows how many of the last 5
days were.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from statistics import median


@dataclass(frozen=True)
class ConsistencyParams:
    days: int = 5  # the tray counts consistent days among the last this many
    history_days: int = 14  # the usual start time is learned from this many days
    tolerance: timedelta = timedelta(minutes=30)
    min_days: int = 3  # fewer days with a session → no usual time yet


@dataclass(frozen=True)
class Consistency:
    usual: time | None  # None: not enough days yet
    consistent_days: int  # among the last `days` (a day without a session counts as not)
    days: int


def _minutes_after(start: datetime, day_starts: time) -> float:
    """Minutes since the day started (04:00), so starts after midnight sort last, not first."""
    local = start.astimezone()
    minutes = local.hour * 60 + local.minute - (day_starts.hour * 60 + day_starts.minute)
    return minutes % (24 * 60)


def consistency(first_starts: dict[date, datetime], today: date, day_starts: time,
                params: ConsistencyParams = ConsistencyParams()) -> Consistency:
    """`first_starts`: each day's first session start. Today only counts once it has one."""
    history = [first_starts[d] for d in first_starts if 0 <= (today - d).days < params.history_days]
    recent_days = [today - timedelta(days=back) for back in range(params.days + 1)]
    if today not in first_starts:
        recent_days = recent_days[1:]  # today is still open
    recent_days = recent_days[: params.days]
    if len(history) < params.min_days:
        return Consistency(None, 0, params.days)
    usual = median(_minutes_after(s, day_starts) for s in history)
    tolerance = params.tolerance.total_seconds() / 60
    kept = sum(
        1 for d in recent_days
        if d in first_starts and abs(_minutes_after(first_starts[d], day_starts) - usual) <= tolerance
    )
    clock = int(usual + day_starts.hour * 60 + day_starts.minute) % (24 * 60)
    return Consistency(time(clock // 60, clock % 60), kept, params.days)
