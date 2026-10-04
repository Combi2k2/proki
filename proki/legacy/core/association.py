"""Which windows contribute to which goal, learned from data (the user's design).

Over time proki sees pairs (T, W): T = the goal group of the active task (the
session's group), or "open" when no task is active; W = the window in focus (the
site's domain or the app). A window whose share of time is clearly higher while a
goal's task is active than overall contributes to that goal.

- Pairs count by minutes; pairs with an active task weigh fully, "open" ones less
  (most of the time no task is active, and that time says little).
- lift(T, W) = P(W | T) / P(W), from the weighted minutes.
- A rule (core/rule.py) on the lift: threshold 1.5 (softness 0.3), active only with
  enough minutes of W during T. It classifies (chance ≥ 50% → contributes), so the
  result is stable rather than sampled.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from proki.core.events import Segment
from proki.legacy.rules.base import Rule, RuleParams

OPEN = None  # no active task


@dataclass(frozen=True)
class AssociationParams:
    lookback: timedelta = timedelta(days=28)
    open_weight: float = 0.25  # an "open" minute counts this much
    lift: float = 1.5  # threshold: W's share during T this many times its overall share → 50%
    softness: float = 0.3
    min_minutes: float = 30  # W during T at least this long before judging


@dataclass(frozen=True)
class Pair:
    group: int
    window: str
    lift: float
    minutes: float  # unweighted minutes of W during T


class Contributes(Rule[Pair]):
    def __init__(self, params: AssociationParams = AssociationParams()):
        super().__init__(RuleParams(threshold=params.lift, softness=params.softness))
        self.min_minutes = params.min_minutes

    def measure(self, pair: Pair) -> float:
        return pair.lift

    def active(self, pair: Pair) -> bool:
        return pair.minutes >= self.min_minutes


def pair_minutes(segments: list[Segment], sessions: list[tuple[datetime, datetime, int | None]]
                 ) -> dict[tuple[int | None, str], float]:
    """Minutes per (goal group or OPEN, window)."""
    pairs: dict[tuple[int | None, str], float] = {}
    for s in segments:
        if s.away:
            continue
        total = s.duration.total_seconds() / 60
        in_tasks = 0.0
        for start, end, group in sessions:
            overlap = (min(s.end, end) - max(s.start, start)).total_seconds() / 60
            if group is not None and overlap > 0:
                pairs[(group, s.key)] = pairs.get((group, s.key), 0.0) + overlap
                in_tasks += overlap
        if total - in_tasks > 0:
            pairs[(OPEN, s.key)] = pairs.get((OPEN, s.key), 0.0) + total - in_tasks
    return pairs


def lifts(pairs: dict[tuple[int | None, str], float], params: AssociationParams = AssociationParams()) -> list[Pair]:
    weight = lambda group: params.open_weight if group is OPEN else 1.0
    weighted = {(g, w): m * weight(g) for (g, w), m in pairs.items()}
    total = sum(weighted.values())
    if not total:
        return []
    by_window: dict[str, float] = {}
    by_group: dict[int | None, float] = {}
    for (g, w), m in weighted.items():
        by_window[w] = by_window.get(w, 0.0) + m
        by_group[g] = by_group.get(g, 0.0) + m
    result = []
    for (g, w), m in weighted.items():
        if g is OPEN or not by_group[g]:
            continue
        lift = (m / by_group[g]) / (by_window[w] / total)
        result.append(Pair(g, w, lift, pairs[(g, w)]))
    return result


def contributions(pairs: dict[tuple[int | None, str], float],
                  params: AssociationParams = AssociationParams()) -> dict[str, set[int]]:
    """window → the goal groups it contributes to."""
    rule = Contributes(params)
    result: dict[str, set[int]] = {}
    for pair in lifts(pairs, params):
        if rule.chance(pair) >= 0.5:
            result.setdefault(pair.window, set()).add(pair.group)
    return result
