"""The user's usual "off time": when they typically stop using the computer for a
long while (more than 3 hours straight), learned from their absences.

Off time = the peak of the distribution (smoothed, time of day) of the starts of
absences longer than 3 hours. It is used to catch the end of the workday before
the user is gone:
- a session ending near the off time → remind them to wrap up the day;
- wrap-ups often missed → before the off time, offer an alarm for the wrap-up.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, time, timedelta


@dataclass(frozen=True)
class OffTimeParams:
    min_absence: timedelta = timedelta(hours=3)  # stopping = away longer than this
    bandwidth: timedelta = timedelta(minutes=30)  # smoothing of the distribution
    min_days: int = 5  # days with such a stop needed before trusting the peak
    near: timedelta = timedelta(minutes=30)  # a session ending this close to the off time → wrap-up reminder
    missed_days: int = 5  # look at the last this many workdays ...
    missed_at_least: int = 3  # ... wrap-up missed this often → offer an alarm
    offer_every: timedelta = timedelta(days=7)  # offer the alarm at most this often


DAY = 24 * 60


def _minutes_after(t: time, day_starts: time) -> float:
    """Minutes since the day started (04:00), so 00:30 comes after 23:30, not before."""
    return (t.hour * 60 + t.minute - day_starts.hour * 60 - day_starts.minute) % DAY


def off_time(stops: list[datetime], day_starts: time, params: OffTimeParams = OffTimeParams()) -> time | None:
    """The most common time of day the user stops (the peak), or None with too few days of data."""
    if len({s.astimezone().date() for s in stops}) < params.min_days:
        return None
    minutes = [_minutes_after(s.astimezone().time(), day_starts) for s in stops]
    band = params.bandwidth.total_seconds() / 60
    best, best_density = 0, -1.0
    for m in range(0, DAY, 5):
        density = sum(math.exp(-0.5 * ((m - x) / band) ** 2) for x in minutes)
        if density > best_density:
            best, best_density = m, density
    clock = (best + day_starts.hour * 60 + day_starts.minute) % DAY
    return time(clock // 60, clock % 60)

def near(now: datetime, off: time | None, params: OffTimeParams = OffTimeParams()) -> bool:
    if off is None:
        return False
    local = now.astimezone()
    return abs(datetime.combine(local.date(), off, local.tzinfo) - local) <= params.near


def often_missed(done: list[bool], params: OffTimeParams = OffTimeParams()) -> bool:
    """`done`: whether the wrap-up was done, for recent workdays (newest first)."""
    recent = done[: params.missed_days]
    return sum(1 for d in recent if not d) >= params.missed_at_least
