"""Rules: two expressions compared, giving a chance of acting rather than a plain yes or no.

    {"name": "busy", "lhs": "keys_5m", "cmp": "gt", "rhs": 30, "softness": 5}

Each side is an expression (a name, a number, `ts_mean(keys, 5)`, ...), compared by `cmp`:
gt (>), ge (>=), lt (<), le (<=), eq (==) or ne (!=).

With no softness, it's a plain comparison: it fires when it holds, else not. With softness s,
the chance moves smoothly as lhs passes rhs:

    gt, ge    50% equal, 73% s above, 88% 2s above, 27% s below, 12% 2s below
    lt, le    the same, mirrored
    eq        100% equal, 61% s apart, 14% 2s apart
    ne        the rest of eq's

So "busy" is 50% at 30 keys a minute, 73% at 35, 88% at 40.

Only numbers are compared (True and False count as 1 and 0): with either side unknown or
text, it doesn't fire.

A rule fires, or not, when it's asked, from the sides as they are then; how often it's asked
is up to whoever asks. Its sides' windows move on every cycle, asked or not.

Several rules decide together by level, the highest first: a level passes when more than half
of its rules fire, and the first that doesn't ends it. To require each of several rules, give
each its own level.
"""

from __future__ import annotations

import operator
from collections.abc import Iterable
from typing import ClassVar

import numpy as np

from proki.core.signals import Signal
from proki.errors import ConfigError, RuleError
from proki.utils import bell, chance, numeric, sigmoid

COMPARE = {
    "gt": operator.gt, "ge": operator.ge,
    "lt": operator.lt, "le": operator.le,
    "eq": operator.eq, "ne": operator.ne,
}
SYMBOL = {"gt": ">", "ge": ">=", "lt": "<", "le": "<=", "eq": "==", "ne": "!="}


class Rule:
    """Two expressions compared, softly (see above). RuleError for a missing side, an unknown
    comparison, a negative softness or a level that isn't a whole number."""

    registry: ClassVar[dict[str, Rule]] = {}  # every rule, by name

    def __init__(
        self,
        name: str,
        lhs: str | float | None = None,
        cmp: str | None = None,
        rhs: str | float | None = None,
        softness: float = 0.0,
        level: int = 1,
        desc: str = "",
    ):
        if not name:    raise RuleError("rule name can't be empty")
        try:
            if lhs is None: raise RuleError("lhs is missing")
            if rhs is None: raise RuleError("rhs is missing")
            if cmp is None or cmp not in COMPARE:
                raise RuleError(f"compare operator has to be one of {', '.join(COMPARE)}")
            if not numeric(softness):
                raise RuleError(f"softness is a number ({softness!r})")
            if softness < 0:
                raise RuleError("softness can't be negative")
            if isinstance(level, bool) or not isinstance(level, int):
                raise RuleError(f"level is a whole number ({level!r})")

            self.name = name
            self.desc = desc  # what it's for, in a line
            self.lhs = Signal(f"{name}.lhs", str(lhs))  # named: moved on every cycle, like any signal
            self.rhs = Signal(f"{name}.rhs", str(rhs))
            self.lhs.inputs, self.rhs.inputs  # compiled now: a mistake shows with the rule's name
            self.cmp = cmp
            self.softness = softness
            self.level = level
        except ConfigError as e:
            raise e.within(f"rule {name!r}") from None
        Rule.registry[name] = self

    def chance(self) -> float:
        """Its chance of firing now, from 0 to 1."""
        a = self.lhs.current()
        b = self.rhs.current()
        if not isinstance(a, int | float):  return 0.0
        if not isinstance(b, int | float):  return 0.0
        if self.softness == 0:
            return 1.0 if COMPARE[self.cmp](a, b) else 0.0

        z = (a - b) / self.softness
        if self.cmp in ("gt", "ge"):    return sigmoid(z)
        if self.cmp in ("lt", "le"):    return sigmoid(-z)
        if self.cmp == "eq":            return bell(z)
        return 1 - bell(z)

    def decide(self, rng: np.random.Generator | None = None) -> bool:
        """Whether it fires now, drawn at its chance."""
        return chance(self.chance(), rng)

    def __repr__(self) -> str:
        soft = f" ~{self.softness:g}" if self.softness else ""
        return f"<Rule {self.name}: {self.lhs.expr} {SYMBOL[self.cmp]} {self.rhs.expr}{soft} (level {self.level})>"

    @classmethod
    def vote(cls, rules: Iterable[Rule], rng: np.random.Generator | None = None) -> bool:
        """Whether `rules` fire together now: level by level, the highest first, a level passing
        when more than half of its rules fire. The first that doesn't ends it: no; the ones
        below aren't asked."""
        levels: dict[int, list[Rule]] = {}
        for rule in rules:
            levels.setdefault(rule.level, []).append(rule)
        for level in sorted(levels, reverse=True):
            fired = sum(rule.decide(rng) for rule in levels[level])
            if fired * 2 <= len(levels[level]):
                return False
        return True
