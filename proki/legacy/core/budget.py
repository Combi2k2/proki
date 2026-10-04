"""The shallow-work budget (Deep Work, rule 4): how much of the day goes to shallow work.

A rule (core/rule.py): the quantity is the shallow share of today's time at the
computer; the threshold is the limit (50% chance of a prompt there), soft around
it. Active only after an hour at the computer (too early to judge before). The
chance is per check, checked every 30 minutes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from proki.legacy.rules.base import Cadence

AWAY = {"away"}


@dataclass(frozen=True)
class BudgetParams:
    limit: float = 0.30  # the threshold: share of active time for shallow work (50% chance per check there)
    softness: float = 0.05  # 25% → 27%, 35% → 73%, 40% → 88% per check
    check_every: timedelta = timedelta(minutes=30)
    min_active: timedelta = timedelta(hours=1)  # the rule's range: not before this much time at the computer


@dataclass(frozen=True)
class ShallowShare:
    shallow: int  # minutes
    active: int  # minutes at the computer (not away)

    @property
    def share(self) -> float:
        return self.shallow / self.active if self.active else 0.0


def shallow_share(minutes_by_activity: dict[str, int]) -> ShallowShare:
    active = sum(m for activity, m in minutes_by_activity.items() if activity not in AWAY)
    return ShallowShare(minutes_by_activity.get("shallow", 0), active)


class ShallowBudget:
    """Every `check_every`, samples whether to mention the budget."""

    def __init__(self, params: BudgetParams = BudgetParams(), rng: random.Random | None = None):
        from proki.legacy.rules.budget import BudgetRule

        self.rule = BudgetRule(params, rng)
        self.cadence = Cadence(params.check_every)

    def should_prompt(self, now: datetime, today: ShallowShare) -> bool:
        if not self.rule.active(today) or not self.cadence.due(now):
            return False
        return self.rule.decide(today)
