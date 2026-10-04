"""One entry per minute: the focus intensity and what you mostly did.

A minute [m, m + 1 min) gets:
- intensity: the main-window focus intensity at its end (None when mostly away)
- activity:  the label with the most time in that minute (deep, shallow,
             distraction, neutral, untracked, unclassified, away), or None
             when there's no data at all (e.g. ActivityWatch wasn't running)

"Deep" is not stored: it's intensity ≥ threshold, decided when reading, so a
new threshold also re-grades past days.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from proki.legacy.core.categories import label
from proki.core.events import Segment
from proki.legacy.focus import FocusParams, moment

MINUTE = timedelta(minutes=1)


@dataclass(frozen=True)
class MinuteEntry:
    minute: datetime  # start of the minute, UTC
    intensity: float | None
    activity: str | None


def minute_floor(t: datetime) -> datetime:
    return t.replace(second=0, microsecond=0)


def score_minutes(
    segments: list[Segment], start: datetime, end: datetime, params: FocusParams
) -> list[MinuteEntry]:
    """Entries for every whole minute from `start` up to (not including) the minute containing `end`.

    `segments` should reach back 2 × the main window before `start`.
    """
    ordered = sorted(segments, key=lambda s: s.start)
    starts = [s.start for s in ordered]
    # latest end so far: never decreases, so it can be binary-searched. Every
    # segment before the first index whose running end passes t ended by t.
    running_end, latest = [], None
    for s in ordered:
        latest = s.end if latest is None or s.end > latest else latest
        running_end.append(latest)
    reach = 2 * params.main_horizon  # the window plus the history `since_last_use` looks at
    entries = []
    minute = minute_floor(start)
    while minute + MINUTE <= end:
        stop = minute + MINUTE
        # only the segments that can matter for this minute, instead of the whole day
        lo = bisect_right(running_end, stop - reach)
        hi = bisect_left(starts, stop)
        nearby = ordered[lo:hi]
        m = moment(nearby, stop, params.main_horizon, params)
        entries.append(MinuteEntry(minute, m.intensity, _dominant_activity(nearby, minute, stop)))
        minute = stop
    return entries


def _dominant_activity(segments: list[Segment], start: datetime, end: datetime) -> str | None:
    seconds: dict[str, float] = defaultdict(float)
    for s in segments:
        overlap = (min(s.end, end) - max(s.start, start)).total_seconds()
        if overlap > 0:
            seconds[label(s)] += overlap
    return max(seconds, key=seconds.get) if seconds else None
