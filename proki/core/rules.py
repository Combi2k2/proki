"""Rules: a soft comparison of two expressions, the chance of doing something now.

A `Rule` compares two expressions, `lhs` and `rhs` (each a signal expression: a name, a
number, `ts_mean(keys, 5)`, ...) with `cmp`, one of gt, ge, lt, le, eq, ne, and turns it
into a chance of firing, in [0, 1]:

    {"name": "busy", "lhs": "keys_5m", "cmp": "gt", "rhs": 30, "softness": 5}

`softness` s is like an LLM's temperature; with z = (lhs - rhs) / s:

    gt, ge      σ(z): equal → 50%, ± s → 73% / 27%, ± 2s → 88% / 12%
    lt, le      σ(-z): the same, mirrored
    eq          exp(-z² / 2): 1 when equal, 61% at ± s, 14% at ± 2s
    ne          1 - that
    softness 0  (the default) the comparison itself: 1 when it holds, else 0; so ge and
                le differ from gt and lt only here

Rules compare numbers only (true / false count as 1 / 0): a side that isn't a number, text
or unknown (None), never fires. A rule keeps no history: `decide()` samples the
chance at the moment, and whoever asks decides how often, since the chance is per asking.
Each side is a hidden signal (`<rule>.lhs`, `<rule>.rhs`: names expressions can't use),
so its windows move on every cycle. Every rule is kept in `Rule.registry` by name.

Rules trigger together by `Rule.vote()`, level by level, the highest first: a level approves
when most of its rules fire; one that doesn't stops the vote there.
"""

from __future__ import annotations

import operator
from collections.abc import Iterable
from typing import ClassVar

import numpy as np

from proki.core.signals import Signal
from proki.errors import ConfigError, RuleError
from proki.utils import bell, chance, is_number, sigmoid

COMPARE = {
    "gt": operator.gt, "ge": operator.ge,
    "lt": operator.lt, "le": operator.le,
    "eq": operator.eq, "ne": operator.ne,
}
SYMBOL = {"gt": ">", "ge": ">=", "lt": "<", "le": "<=", "eq": "==", "ne": "!="}


class Rule:
    registry: ClassVar[dict[str, Rule]] = {}  # every rule, by name

    def __init__(
        self,
        name: str,
        lhs: str | float | None = None,
        cmp: str | None = None,
        rhs: str | float | None = None,
        softness: float = 0.0,
        level: int = 1,
    ):
        if not name:    raise RuleError("rule name can't be empty")
        try:
            if lhs is None: raise RuleError("lhs is missing")
            if rhs is None: raise RuleError("rhs is missing")
            if cmp is None or cmp not in COMPARE:
                raise RuleError(f"compare operator has to be one of {', '.join(COMPARE)}")
            if isinstance(softness, bool) or not isinstance(softness, int | float):
                raise RuleError(f"softness is a number ({softness!r})")
            if softness < 0:
                raise RuleError("softness can't be negative")
            if isinstance(level, bool) or not isinstance(level, int):
                raise RuleError(f"level is a whole number ({level!r})")

            self.name = name
            self.lhs = Signal(f"{name}.lhs", str(lhs)); self.lhs.inputs
            self.rhs = Signal(f"{name}.rhs", str(rhs)); self.rhs.inputs
            self.cmp = cmp
            self.softness = softness
            self.level = level
        except ConfigError as e:
            raise e.within(f"rule {name!r}") from None
        Rule.registry[name] = self

    def chance(self) -> float:
        """The chance of firing now, at the sides' current values."""
        a = self.lhs.current()
        b = self.rhs.current()
        if not is_number(a):    return 0.0
        if not is_number(b):    return 0.0
        if self.softness == 0:
            return 1.0 if COMPARE[self.cmp](a, b) else 0.0

        z = (a - b) / self.softness
        if self.cmp in ("gt", "ge"):    return sigmoid(z)
        if self.cmp in ("lt", "le"):    return sigmoid(-z)
        if self.cmp == "eq":            return bell(z)
        return 1 - bell(z)

    def decide(self, rng: np.random.Generator | None = None) -> bool:
        """Fire or not, now: the chance at the moment, sampled."""
        return chance(self.chance(), rng)

    def __repr__(self) -> str:
        soft = f" ~{self.softness:g}" if self.softness else ""
        return f"<Rule {self.name}: {self.lhs.expr} {SYMBOL[self.cmp]} {self.rhs.expr}{soft} (level {self.level})>"

    @classmethod
    def vote(cls, rules: Iterable[Rule], rng: np.random.Generator | None = None) -> bool:
        """Whether `rules` trigger, now: level by level, the highest first, each by a majority
        of its rules (more than half fire; each rule sampled once); a level that doesn't
        approve stops the vote there, so lower levels aren't asked."""
        levels: dict[int, list[Rule]] = {}
        for rule in rules:
            levels.setdefault(rule.level, []).append(rule)
        for level in sorted(levels, reverse=True):
            fired = sum(rule.decide(rng) for rule in levels[level])
            if fired * 2 <= len(levels[level]):
                return False
        return True
