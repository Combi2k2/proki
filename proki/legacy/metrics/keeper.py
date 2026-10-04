"""Keeps the minute ledger up to date and answers "how is today going?"."""

from __future__ import annotations

from datetime import datetime, time
from typing import Callable

from proki.core.events import Segment
from proki.legacy.focus import FocusParams
from proki.legacy.metrics.day import DayScore, day_bounds, summarize_day
from proki.legacy.metrics.ledger import MINUTE, score_minutes
from proki.legacy.core.store import Store

LoadSegments = Callable[[datetime, datetime], list[Segment]]  # categorized segments for a time range


class ScoreKeeper:
    def __init__(
        self,
        store: Store,
        load: LoadSegments,
        params: FocusParams,
        day_starts: time,
    ):
        self.store = store
        self.load = load
        self.params = params
        self.day_starts = day_starts

    def update(self, now: datetime) -> int:
        """Score every finished minute not in the ledger yet (back to the start of today).

        Returns how many minutes were added. The first call after a start fills
        in the day so far from ActivityWatch's history.
        """
        _, day_start, _ = day_bounds(now, self.day_starts)
        last = self.store.last_minute()
        start = max(day_start, last + MINUTE) if last else day_start
        if start + MINUTE > now:
            return 0
        segments = self.load(start - 2 * self.params.main_horizon, now)
        entries = score_minutes(segments, start, now, self.params)
        self.store.save_minutes(entries)
        return len(entries)

    def today(self, now: datetime, goal_minutes: int = 0) -> DayScore:
        day, start, end = day_bounds(now, self.day_starts)
        return summarize_day(day, self.store.minutes(start, end), self.params.deep_threshold, goal_minutes)
