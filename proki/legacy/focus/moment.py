"""Focus intensity at one moment: depth × stability × continuity over [t − τ, t]."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from proki.legacy.core.events import Segment
from proki.legacy.focus.continuity import continuity, mean_dwell_seconds
from proki.legacy.focus.depth import depth
from proki.legacy.focus.params import FocusParams
from proki.legacy.focus.stability import effective_items, fit, hit_rate
from proki.legacy.focus.window import Window, slice_window


@dataclass(frozen=True)
class Moment:
    """The score and every component behind it, so each can be inspected and tuned."""

    window: Window
    depth: float | None
    fit: float
    hit_rate: float
    continuity: float
    defined: bool  # enough of the window was active (and not only neutral) to judge

    @property
    def stability(self) -> float:
        return self.fit * self.hit_rate

    @property
    def intensity(self) -> float | None:
        if not self.defined or self.depth is None:
            return None
        return self.depth * self.stability * self.continuity

    # handy for display
    @property
    def effective_items(self) -> float:
        return effective_items(self.window)

    @property
    def mean_dwell_seconds(self) -> float:
        return mean_dwell_seconds(self.window)


def moment(segments: list[Segment], end: datetime, horizon: timedelta, params: FocusParams) -> Moment:
    window = slice_window(segments, end, horizon)
    return Moment(
        window=window,
        depth=depth(window, params),
        fit=fit(window, params),
        hit_rate=hit_rate(window),
        continuity=continuity(window, params),
        defined=window.active_seconds >= horizon.total_seconds() * params.min_active_share,
    )


def series(
    segments: list[Segment],
    end: datetime,
    horizon: timedelta,
    span: timedelta,
    step: timedelta,
    params: FocusParams,
) -> list[Moment]:
    """`moment` at every `step` over the last `span`, oldest first."""
    count = int(span / step)
    return [moment(segments, end - step * i, horizon, params) for i in range(count, -1, -1)]
