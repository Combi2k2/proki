"""Session history and the chain of kept blocks (plain functions over stored data)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from proki.legacy.metrics.ledger import MinuteEntry


@dataclass(frozen=True)
class SessionSummary:
    started_at: datetime
    ended_at: datetime | None  # None while running
    deep_minutes: int
    pokes: int
    ended_by: str | None  # 'user', 'away', or None while running
    group_id: int | None = None  # the goal group worked on


def deep_minutes(entries: list[MinuteEntry], start: datetime, end: datetime, threshold: float) -> int:
    """Minutes in [start, end) whose focus intensity reached the threshold."""
    return sum(
        1 for e in entries
        if start <= e.minute < end and e.intensity is not None and e.intensity >= threshold
    )


@dataclass(frozen=True)
class DayOutcome:
    """How a scheduled day went: did the user keep the block, skip it, or neither yet?"""

    day: date
    kept: bool
    skipped: bool = False


def chain_length(outcomes: list[DayOutcome], today: date) -> int:
    """Consecutive kept days up to today. Today only counts once kept (it isn't
    over yet), days without a block are ignored, a missed or skipped day breaks it."""
    chain = 0
    for outcome in sorted(outcomes, key=lambda o: o.day, reverse=True):
        if outcome.day > today:
            continue
        if outcome.kept:
            chain += 1
        elif outcome.day == today and not outcome.skipped:
            continue  # today is still open
        else:
            break
    return chain


def block_window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """Sessions starting in this window count toward the block (a little early is fine)."""
    return start - timedelta(minutes=30), end
