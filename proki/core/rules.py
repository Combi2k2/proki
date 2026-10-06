"""Rules: a comparison of two expressions that gives a chance of acting, not a plain yes/no.

    {"name": "busy", "lhs": "keys_5m", "cmp": "gt", "rhs": 30, "softness": 5}

`lhs` and `rhs` are expressions (a name, a number, `ts_mean(keys, 5)`, ...), compared
with `cmp`: gt (>), ge (>=), lt (<), le (<=), eq (==) or ne (!=).

Softness: with softness 0 (the default), the rule is a plain comparison: it fires
(chance 1) when it holds, else not (0). With softness s > 0, the chance rises smoothly
as lhs passes rhs, like an LLM's temperature. With z = (lhs - rhs) / s:

    gt, ge   equal: 50%, s above: 73%, 2s above: 88%, s below: 27%, 2s below: 12%
    lt, le   the same, mirrored
    eq       equal: 100%, s apart: 61%, 2s apart: 14%
    ne       100% minus eq's chance

So "busy" above is 50% at 30 keys a minute, 73% at 35, 88% at 40.

Only numbers are compared (True / False count as 1 / 0). If either side is unknown or
text, the rule doesn't fire.

A rule keeps no history: `decide()` samples its chance at that moment, so how often it
gets the chance to fire is up to whoever asks (a reaction's `every`). Each side is a hidden
signal (`<rule>.lhs`, `<rule>.rhs`), so windows in it move on every cycle.

Several rules decide together with `Rule.vote()`, by `level`, highest first: a level passes
when more than half of its rules fire, and the vote stops at the first level that doesn't.
To require all of several rules, give each its own level.
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
    """A soft comparison of two expressions (see above)."""

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
            self.lhs = Signal(f"{name}.lhs", str(lhs))
            self.rhs = Signal(f"{name}.rhs", str(rhs))
            self.lhs.inputs, self.rhs.inputs  # compiled now: a mistake shows with the rule's name
            self.cmp = cmp
            self.softness = softness
            self.level = level
        except ConfigError as e:
            raise e.within(f"rule {name!r}") from None
        Rule.registry[name] = self

    def chance(self) -> float:
        """The chance of firing now, from 0 to 1, given the sides' current values."""
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
        """Whether it fires now: a random draw with its current chance."""
        return chance(self.chance(), rng)

    def __repr__(self) -> str:
        soft = f" ~{self.softness:g}" if self.softness else ""
        return f"<Rule {self.name}: {self.lhs.expr} {SYMBOL[self.cmp]} {self.rhs.expr}{soft} (level {self.level})>"

    @classmethod
    def vote(cls, rules: Iterable[Rule], rng: np.random.Generator | None = None) -> bool:
        """Whether `rules` trigger now. They're grouped by level and voted level by level,
        highest first: a level passes when more than half of its rules fire (each drawn
        once). The first level that doesn't pass ends the vote with False. Lower levels
        aren't drawn."""
        levels: dict[int, list[Rule]] = {}
        for rule in rules:
            levels.setdefault(rule.level, []).append(rule)
        for level in sorted(levels, reverse=True):
            fired = sum(rule.decide(rng) for rule in levels[level])
            if fired * 2 <= len(levels[level]):
                return False
        return True
