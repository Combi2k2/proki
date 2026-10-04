"""Summary of a period (an hour, a work block, a day) from one-minute moment scores."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from proki.core.events import Category, Segment
from proki.legacy.focus.moment import series
from proki.legacy.focus.params import FocusParams
from proki.legacy.focus.window import slice_window

STEP = timedelta(minutes=1)


@dataclass(frozen=True)
class Period:
    start: datetime
    end: datetime
    intensities: list[float | None]  # one per minute, main horizon; None = mostly away
    mean_intensity: float | None
    deep_minutes: int  # minutes with intensity ≥ deep_threshold
    longest_deep_streak: int  # in minutes
    intrusions_per_hour: float  # switches into a distraction
    coverage: float  # share of the period that was active

    @property
    def minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60


def summarize(segments: list[Segment], start: datetime, end: datetime, params: FocusParams) -> Period:
    """`segments` should reach back at least 2 × the main horizon before `start`."""
    moments = series(segments, end, params.main_horizon, end - start, STEP, params)
    intensities = [m.intensity for m in moments]
    defined = [i for i in intensities if i is not None]
    deep = [i is not None and i >= params.deep_threshold for i in intensities]

    whole = slice_window(segments, end, end - start)
    hours = (end - start).total_seconds() / 3600
    intrusions = sum(s.to_category is Category.DISTRACTION for s in whole.switches)

    return Period(
        start=start,
        end=end,
        intensities=intensities,
        mean_intensity=sum(defined) / len(defined) if defined else None,
        deep_minutes=sum(deep),
        longest_deep_streak=_longest_run(deep),
        intrusions_per_hour=intrusions / hours if hours else 0.0,
        coverage=whole.active_seconds / (end - start).total_seconds() if end > start else 0.0,
    )


def _longest_run(flags: list[bool]) -> int:
    best = run = 0
    for flag in flags:
        run = run + 1 if flag else 0
        best = max(best, run)
    return best
