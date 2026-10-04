"""The rhythmic routine day to day: today's block, today's sessions, the chain.

Glue between stored data (plans, sessions, focus minutes) and the pure logic in
schedule.py and history.py, like scoreboard/keeper.py is for the scoreboard.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from proki.legacy.metrics.history import DayOutcome, SessionSummary, block_window, chain_length, deep_minutes
from proki.legacy.core.schedule import Block, RhythmParams, block_for
from proki.legacy.metrics.day import day_bounds
from proki.legacy.core.store import Store

CHAIN_LOOKBACK_DAYS = 120


class Rhythm:
    def __init__(self, store: Store, params: RhythmParams, day_starts: time, deep_threshold: float):
        self.store = store
        self.params = params
        self.day_starts = day_starts
        self.deep_threshold = deep_threshold

    def today(self, now: datetime) -> date:
        return day_bounds(now, self.day_starts)[0]

    def block(self, day: date, tz) -> Block | None:
        return block_for(day, self.params, self.store.get_plan(day), tz)

    def sessions(self, start: datetime, end: datetime, now: datetime) -> list[SessionSummary]:
        entries = self.store.minutes(start - timedelta(hours=12), end + timedelta(hours=12))
        result = []
        for started, ended, pokes, ended_by, group_id in self.store.sessions_between(start, end):
            result.append(SessionSummary(
                started, ended, deep_minutes(entries, started, ended or now, self.deep_threshold), pokes, ended_by,
                group_id,
            ))
        return result

    def todays_sessions(self, now: datetime) -> list[SessionSummary]:
        _, start, end = day_bounds(now, self.day_starts)
        return self.sessions(start, end, now)

    def outcome(self, day: date, tz, now: datetime) -> DayOutcome | None:
        block = self.block(day, tz)
        if block is None:
            return None
        start, end = block_window(block.start, block.end)
        kept = any(s.deep_minutes >= self.params.kept_deep_minutes for s in self.sessions(start, end, now))
        return DayOutcome(day, kept, skipped="skipped" in self.store.block_actions(day))

    def chain(self, now: datetime) -> int:
        today = self.today(now)
        tz = now.astimezone().tzinfo
        outcomes = []
        for back in range(CHAIN_LOOKBACK_DAYS):
            outcome = self.outcome(today - timedelta(days=back), tz, now)
            if outcome is not None:
                outcomes.append(outcome)
                if not outcome.kept and back > 0:
                    break  # the chain can't reach further back than a broken day
        return chain_length(outcomes, today)

    def first_starts(self, now: datetime, days: int) -> dict[date, datetime]:
        """Each day's first session start over the last `days` days (today included)."""
        _, today_start, today_end = day_bounds(now, self.day_starts)
        result: dict[date, datetime] = {}
        for started, *_ in self.store.sessions_between(today_start - timedelta(days=days - 1), today_end):
            day, _, _ = day_bounds(started, self.day_starts)
            result.setdefault(day, started)  # sessions come in start order
        return result
