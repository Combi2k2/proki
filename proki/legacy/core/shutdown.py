"""The shutdown ritual (Deep Work, rule 1): a clear end to the workday.

At the end of the workday proki walks the user through closing it: today's notes
(each becomes a task or stays a note), a wrap-up in their own words (anything
still open becomes a task, so it can be let go), a look at tomorrow, then
"shutdown complete". After that, work questions (capture) stop for the day.

When to offer it: two rules (core/rule.py) that must both hold, sampled every
few minutes:
- the time of day, a soft threshold at the shutdown time (18:00 → 50%; 16:00 1%,
  17:00 10%, 17:30 25%, 18:30 75%, 19:00 90%), active from 3 hours before it;
- low focus, a soft threshold below the 5-min focus score of 0.3 (unfocused or
  idle → ~100%), active only below 0.6: never while the user is focused.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, time, timedelta


DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass(frozen=True)
class ShutdownParams:
    enabled: bool = True
    time: time = time(18, 0)  # the end of the workday: the time rule's threshold
    days: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri")
    snooze: timedelta = timedelta(minutes=30)  # "ask later"
    time_softness: timedelta = timedelta(minutes=30 / math.log(3))  # ±30 min → 25% / 75%
    time_from: timedelta = timedelta(hours=3)  # the time rule is active from this long before the shutdown time
    focus_threshold: float = 0.3  # low focus: 50% here (5-min focus score)
    focus_softness: float = 0.07  # 0.15 → 89%, 0.45 → 11%
    focused: float = 0.6  # at or above this the user is focused: never offered
    check_every: timedelta = timedelta(minutes=5)


def workday(day: date, params: ShutdownParams) -> bool:
    return params.enabled and DAY_NAMES[day.weekday()] in params.days


