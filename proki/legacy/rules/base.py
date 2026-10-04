"""The rule abstraction: a measured quantity against a soft threshold.

Almost everything proki decides ("prompt now?", "is focus low?") is a quantity
against a threshold. A rule:

- `measure(context)`: the quantity (None = can't tell → never fires);
- `threshold`: the value where the chance of firing is 50%;
- `softness`: how gradual the change is, in the quantity's units: the chance is
  an S-curve (logistic), σ((value − threshold) / softness): ±1 softness from the
  threshold → 27% / 73%, ±2 → 12% / 88%. 0 = a hard step (fires from the threshold on);
- `direction`: +1 fires above the threshold, −1 below it;
- `range`: where the rule is active at all (bounds of the quantity; either may be
  None). Outside it, it never fires. A rule can also narrow this with `active()`,
  for conditions on the context rather than on the quantity;
- `decide(context)`: measure → chance → sample (a hard rule is simply 0 or 1).

Optionally `steps` replaces the curve with exact chances from given values on,
for rules whose numbers the user set exactly (e.g. the routine questions).
Rules combine with `AllOf` (chances multiplied: all must hold).
"""

from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Generic, TypeVar

C = TypeVar("C")


@dataclass(frozen=True)
class RuleParams:
    threshold: float
    softness: float = 0.0  # 0 = hard
    direction: int = 1  # +1: fire above the threshold; −1: below
    range: tuple[float | None, float | None] = (None, None)  # active only for values in [low, high]
    steps: tuple[tuple[float, float], ...] = ()  # optional exact chances: (from this value on, chance), ascending


def chance_at(value: float | None, p: RuleParams) -> float:
    """The chance of firing for a measured value."""
    if value is None:
        return 0.0
    low, high = p.range
    if (low is not None and value < low) or (high is not None and value > high):
        return 0.0
    if p.steps:
        chance = 0.0
        for start, step_chance in p.steps:
            if value >= start:
                chance = step_chance
        return chance
    x = p.direction * (value - p.threshold)
    if p.softness <= 0:
        return 1.0 if x >= 0 else 0.0
    z = x / p.softness
    if z < -50:
        return 0.0
    return 1 / (1 + math.exp(-z))


class Rule(ABC, Generic[C]):
    params: RuleParams

    def __init__(self, params: RuleParams | None = None, rng: random.Random | None = None):
        if params is not None:
            self.params = params
        self.rng = rng or random.Random()

    @abstractmethod
    def measure(self, context: C) -> float | None:
        """The quantity this rule watches; None when it can't be told."""

    def active(self, context: C) -> bool:
        """Conditions beyond the quantity's range (e.g. only on workdays). Default: always."""
        return True

    def chance(self, context: C) -> float:
        if not self.active(context):
            return 0.0
        return chance_at(self.measure(context), self.params)

    def decide(self, context: C) -> bool:
        p = self.chance(context)
        return p >= 1.0 or (p > 0.0 and self.rng.random() < p)


class AllOf(Rule[C]):
    """Several rules that must all hold: their chances multiply, sampled once."""

    def __init__(self, *rules: Rule[C], rng: random.Random | None = None):
        super().__init__(RuleParams(threshold=0.0), rng)
        self.rules = rules

    def measure(self, context: C) -> float | None:
        return None  # not used: the chance comes from the parts

    def chance(self, context: C) -> float:
        if not self.active(context):
            return 0.0
        result = 1.0
        for rule in self.rules:
            result *= rule.chance(context)
            if result == 0.0:
                break
        return result


class Cadence:
    """How often a sampled rule is evaluated: its chance is per check, so checks are spaced."""

    def __init__(self, every: timedelta):
        self.every = every
        self.last: datetime | None = None

    def due(self, now: datetime) -> bool:
        if self.last is not None and now - self.last < self.every:
            return False
        self.last = now
        return True
