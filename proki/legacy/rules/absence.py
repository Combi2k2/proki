"""Whether to ask "what did you do?" about an absence (core/routines.py)."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from proki.legacy.rules.base import Rule, RuleParams

if TYPE_CHECKING:
    from proki.legacy.core.routines import Absence


class AskRule(Rule["Absence"]):
    """Whether to ask about an absence (core/rule.py): the quantity is its length in
    minutes; threshold 5 min; the chances are the user's exact numbers (steps):
    5–20 min 20% (toilet, coffee: mostly not worth asking), 20–60 min 60%,
    1–3 h 80%, over 3 h 50% (sleep, a day out, offline work)."""

    params = RuleParams(threshold=5, range=(5, None), steps=((5, 0.2), (20, 0.6), (60, 0.8), (180, 0.5)))

    def __init__(self, always: bool = False, rng: random.Random | None = None):
        # always (for trying it out): every absence from 5 minutes on
        super().__init__(RuleParams(threshold=5) if always else None, rng)

    def measure(self, absence: "Absence") -> float:
        return absence.duration.total_seconds() / 60


class StillThere(Rule[float]):
    """Don't ask after all: openjev is this sure the person stayed at the computer
    (watching, listening, reading). The quantity is openjev's probability; hard threshold."""

    def __init__(self, threshold: float = 0.7):
        super().__init__(RuleParams(threshold=threshold))

    def measure(self, probability: float) -> float:
        return probability
