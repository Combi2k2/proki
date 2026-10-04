"""The shallow-work budget rule: shallow share of today's time at the computer vs. the limit."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from proki.legacy.rules.base import Rule, RuleParams

if TYPE_CHECKING:
    from proki.legacy.core.budget import BudgetParams, ShallowShare


class BudgetRule(Rule["ShallowShare"]):
    def __init__(self, params: "BudgetParams", rng: random.Random | None = None):
        super().__init__(RuleParams(threshold=params.limit, softness=params.softness), rng)
        self.min_active = params.min_active.total_seconds() / 60

    def measure(self, today: ShallowShare) -> float:
        return today.share

    def active(self, today: ShallowShare) -> bool:
        return today.active >= self.min_active
