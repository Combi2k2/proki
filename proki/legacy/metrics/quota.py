"""The daily deep-work quota: 4 to 10 hours, rising in 1-hour steps.

- Within a day: once today's deep minutes pass 80% of today's quota, today's quota
  rises by one step (there's always a next target), up to the maximum.
- Permanently: passing 80% of the base quota on 3 days in a row raises the base
  by one step. The quota never goes down on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class QuotaParams:
    start: int = 240  # minutes: the first base quota (4 h)
    step: int = 60
    maximum: int = 600  # 10 h
    raise_at: float = 0.8  # share of the quota that triggers a raise
    streak_days: int = 3  # days in a row above raise_at × base to raise the base


def today_quota(base: int, deep_minutes: int, p: QuotaParams) -> int:
    quota = base
    while deep_minutes >= p.raise_at * quota and quota + p.step <= p.maximum:
        quota += p.step
    return quota


def next_base(base: int, deep_by_day: dict[date, int], today: date, p: QuotaParams) -> int:
    """The base quota for `today`, given the finished days before it.

    Raised by one step when each of the last `streak_days` days (all before today)
    passed raise_at × base.
    """
    days = [today - timedelta(days=i) for i in range(1, p.streak_days + 1)]
    if all(deep_by_day.get(d, 0) >= p.raise_at * base for d in days):
        return min(base + p.step, p.maximum)
    return base


class QuotaKeeper:
    """The base quota over time (stored), and today's quota."""

    def __init__(self, store, params: QuotaParams, day_starts, deep_threshold: float):
        self.store = store
        self.params = params
        self.day_starts = day_starts
        self.deep_threshold = deep_threshold

    def base(self, now) -> int:
        """The base for today; recalculated once per day from the days before."""
        from proki.legacy.metrics.day import day_bounds

        today, _, _ = day_bounds(now, self.day_starts)
        base = int(self.store.get_state("quota_base") or self.params.start)
        if self.store.get_state("quota_base_day") != today.isoformat():
            base = next_base(base, self._deep_by_day(today), today, self.params)
            self.store.set_state("quota_base", str(base))
            self.store.set_state("quota_base_day", today.isoformat())
        return base

    def today(self, now, deep_minutes_today: int) -> int:
        return today_quota(self.base(now), deep_minutes_today, self.params)

    def _deep_by_day(self, today: date) -> dict[date, int]:
        from datetime import datetime

        from proki.legacy.metrics.day import summarize_day

        result = {}
        for back in range(1, self.params.streak_days + 1):
            day = today - timedelta(days=back)
            start = datetime.combine(day, self.day_starts).astimezone()
            entries = self.store.minutes(start, start + timedelta(days=1))
            result[day] = summarize_day(day, entries, self.deep_threshold, 0).deep_minutes
        return result
