"""How well does the focus score agree with the user's own ratings?

Agreement is Spearman's rank correlation (−1..1): does the score go up when
the rating goes up? Only the ordering matters, so it doesn't matter that a
rating of 3 and a score of 0.42 are on different scales.

`evaluate` scores each component separately; `sweep` tries other values for one
parameter at a time and reports which agree best. Nothing is changed
automatically: the user decides what to put in the config.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from proki.legacy.core.events import Category, Segment
from proki.legacy.focus import FocusParams, moment

MEASURES = {
    "intensity": lambda m: m.intensity,
    "depth": lambda m: m.depth,
    "fit": lambda m: m.fit,
    "hit rate": lambda m: m.hit_rate,
    "continuity": lambda m: m.continuity,
}


@dataclass(frozen=True)
class Agreement:
    correlation: float | None  # None when there are too few usable ratings
    n: int


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    var = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return cov / var if var else None


def evaluate(
    ratings: list[tuple[datetime, int]], segments: list[Segment], params: FocusParams
) -> dict[timedelta, dict[str, Agreement]]:
    """Per window size, how well each measure agrees with the ratings."""
    result = {}
    for horizon in params.horizons:
        moments = [(rating, moment(segments, at, horizon, params)) for at, rating in ratings]
        result[horizon] = {}
        for name, get in MEASURES.items():
            pairs = [(get(m), r) for r, m in moments if get(m) is not None]
            result[horizon][name] = Agreement(spearman([p[0] for p in pairs], [p[1] for p in pairs]), len(pairs))
    return result


def candidates(params: FocusParams) -> dict[str, list[tuple[str, FocusParams]]]:
    """Alternative settings, one parameter at a time."""
    def with_shallow(w: float) -> FocusParams:
        return replace(params, weights={**params.weights, Category.SHALLOW: w})

    def with_main_horizon(minutes: int) -> FocusParams:
        horizons = list(params.horizons)
        horizons[len(horizons) // 2] = timedelta(minutes=minutes)
        return replace(params, horizons=tuple(horizons))

    return {
        "shallow_weight": [(str(w), with_shallow(w)) for w in (0.0, 0.15, 0.3, 0.5)],
        "capacity": [(str(c), replace(params, capacity=c)) for c in (3, 5, 8)],
        "dwell_scale_seconds": [
            (str(s), replace(params, dwell_scale=timedelta(seconds=s))) for s in (10, 20, 40, 60)
        ],
        "main window (minutes)": [(str(m), with_main_horizon(m)) for m in (5, 10, 20)],
    }


def sweep(
    ratings: list[tuple[datetime, int]], segments: list[Segment], params: FocusParams
) -> dict[str, list[tuple[str, Agreement]]]:
    """Agreement of the main-window intensity for each alternative value."""
    result = {}
    for name, options in candidates(params).items():
        result[name] = []
        for label, alternative in options:
            pairs = [
                (m.intensity, r)
                for at, r in ratings
                if (m := moment(segments, at, alternative.main_horizon, alternative)).intensity is not None
            ]
            result[name].append((label, Agreement(spearman([p[0] for p in pairs], [p[1] for p in pairs]), len(pairs))))
    return result


def _ranks(values: list[float]) -> list[float]:
    """Ranks starting at 1; ties get the average of their positions."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks
