"""The shutdown rules: the time of day around the shutdown time × low focus (core/shutdown.py)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

from proki.legacy.rules.base import AllOf, Rule, RuleParams

if TYPE_CHECKING:
    from proki.legacy.core.shutdown import ShutdownParams


@dataclass(frozen=True)
class ShiftContext:
    now: datetime
    day: date  # the "day" now belongs to (before day_starts = the previous one)
    day_starts: time
    intensity: float | None  # 5-min focus score; None = no data (idle, away)


class TimeRule(Rule[ShiftContext]):
    """Minutes past the shutdown time (negative before it)."""

    def __init__(self, params: "ShutdownParams"):
        super().__init__(RuleParams(threshold=0, softness=params.time_softness.total_seconds() / 60,
                                    range=(-params.time_from.total_seconds() / 60, None)))
        self.shutdown = params

    def measure(self, c: ShiftContext) -> float:
        local = c.now.astimezone()
        return (local - datetime.combine(c.day, self.shutdown.time, local.tzinfo)).total_seconds() / 60

    def active(self, c: ShiftContext) -> bool:
        local = c.now.astimezone()
        before_day_end = local < datetime.combine(c.day + timedelta(days=1), c.day_starts, local.tzinfo)
        from proki.legacy.core.shutdown import workday

        return workday(c.day, self.shutdown) and before_day_end


class LowFocusRule(Rule[ShiftContext]):
    """The 5-min focus score, firing below the threshold; no data counts as unfocused."""

    def __init__(self, params: "ShutdownParams"):
        super().__init__(RuleParams(threshold=params.focus_threshold, softness=params.focus_softness,
                                    direction=-1, range=(None, params.focused - 1e-9)))

    def measure(self, c: ShiftContext) -> float:
        return 0.0 if c.intensity is None else c.intensity


def shift_ending(params: "ShutdownParams") -> AllOf[ShiftContext]:
    """The rule for offering the shutdown: near/after the shutdown time, and focus low."""
    return AllOf(TimeRule(params), LowFocusRule(params))
