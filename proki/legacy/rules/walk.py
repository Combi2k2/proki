"""After a session: suggest a thinking walk? (core/meditation.py)"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from proki.legacy.rules.base import Rule, RuleParams

if TYPE_CHECKING:
    from proki.legacy.core.meditation import MeditationParams


class SuggestWalk(Rule[int]):
    """After a session: suggest a walk? The better the session, the more likely (core/rule.py)."""

    def __init__(self, params: "MeditationParams", rng: random.Random | None = None):
        super().__init__(RuleParams(threshold=params.threshold, softness=params.softness,
                                    range=(params.min_deep_minutes, None)), rng)

    def measure(self, session_deep_minutes: int) -> float:
        return session_deep_minutes
