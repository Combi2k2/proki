from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from proki.legacy.core.events import Category


@dataclass(frozen=True)
class FocusParams:
    """Every tunable number of the focus metric. Defaults are starting guesses."""

    # depth.py: how much each kind of time counts. Neutral time is left out entirely.
    weights: dict[Category | None, float] = field(
        default_factory=lambda: {
            Category.DEEP: 1.0,
            Category.SHALLOW: 0.3,
            Category.DISTRACTION: 0.0,
            None: 0.0,  # unclassified or untracked
        }
    )
    # stability.py: items a focused working set can hold before it counts as scattered
    capacity: int = 5
    # continuity.py: mean time per item at which continuity reaches 1 − 1/e ≈ 0.63
    dwell_scale: timedelta = timedelta(seconds=20)
    # moment.py: below this share of active time, the window is mostly away → undefined
    min_active_share: float = 0.25
    # moment.py / period.py: window sizes; the middle one is the main score
    horizons: tuple[timedelta, ...] = (timedelta(minutes=2), timedelta(minutes=5), timedelta(minutes=30))
    # period.py: a minute counts as deep when its main-horizon intensity is at least this
    deep_threshold: float = 0.6
    # depth.py: creating vs. consuming, from input actions per minute (aw-watcher-input).
    # Consuming time counts `consuming` of its category's weight; creating counts fully; in
    # between a soft threshold (50% creating at `creating_at` actions/min). No input data → 1.
    consuming: float = 0.8
    creating_at: float = 10.0
    creating_softness: float = 4.0

    @property
    def main_horizon(self) -> timedelta:
        return self.horizons[len(self.horizons) // 2]
