"""A day's scoreboard from its minute entries."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from proki.legacy.metrics.ledger import MINUTE, MinuteEntry


@dataclass(frozen=True)
class DayScore:
    day: date
    deep_minutes: int  # minutes with intensity ≥ threshold
    longest_streak: int  # longest run of consecutive deep minutes
    current_streak: int  # deep minutes in a row up to the latest minute (0 if not deep now)
    mean_intensity: float | None
    minutes_by_activity: dict[str, int]  # deep, shallow, distraction, neutral, away, ...
    goal_minutes: int

    @property
    def goal_progress(self) -> float:
        return min(1.0, self.deep_minutes / self.goal_minutes) if self.goal_minutes else 0.0


def day_bounds(now: datetime, day_starts: time) -> tuple[date, datetime, datetime]:
    """The "day" `now` belongs to, and its start/end, in local time.

    With day_starts = 04:00, 02:30 still counts as the previous day.
    """
    local = now.astimezone()
    day = local.date() if local.time() >= day_starts else local.date() - timedelta(days=1)
    start = datetime.combine(day, day_starts, local.tzinfo)
    return day, start, start + timedelta(days=1)


def summarize_day(day: date, entries: list[MinuteEntry], threshold: float, goal_minutes: int) -> DayScore:
    entries = sorted(entries, key=lambda e: e.minute)
    deep = [e.intensity is not None and e.intensity >= threshold for e in entries]

    longest = run = 0
    previous: datetime | None = None
    for entry, is_deep in zip(entries, deep):
        contiguous = previous is not None and entry.minute - previous == MINUTE
        run = (run + 1 if contiguous else 1) if is_deep else 0
        longest = max(longest, run)
        previous = entry.minute

    current = 0
    for entry, is_deep in zip(reversed(entries), reversed(deep)):
        if not is_deep:
            break
        current += 1

    scored = [e.intensity for e in entries if e.intensity is not None]
    return DayScore(
        day=day,
        deep_minutes=sum(deep),
        longest_streak=longest,
        current_streak=current,
        mean_intensity=sum(scored) / len(scored) if scored else None,
        minutes_by_activity=dict(Counter(e.activity for e in entries if e.activity)),
        goal_minutes=goal_minutes,
    )
