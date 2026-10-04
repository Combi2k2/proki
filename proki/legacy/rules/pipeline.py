"""Decision pipelines: levels of atomic rules (the user's design).

A pipeline is a list of numbered levels, each a set of rules that vote. A level
approves when enough of its rules fire (by default a majority; a level can ask
for all of them, so its rules can't be outvoted). Level 1 votes first; only if it
approves does the next level vote, and so on. The action happens when every
level approves.

Rules read **signals**: named quantities computed from the current state
("focus_2m", "in_session", ...). `SignalRule` is the generic rule on one named signal
(threshold, softness, direction, range from rules/base.py), so a rule can be
plain data; later these can come from the user's config.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Mapping

from proki.legacy.rules.base import Rule, RuleParams

Signals = Mapping[str, "float | bool | None"]


class SignalRule(Rule[Signals]):
    """A rule on one named signal (booleans count as 0 / 1)."""

    def __init__(self, name: str, threshold: float, softness: float = 0.0, direction: int = 1,
                 range: tuple[float | None, float | None] = (None, None), rng: random.Random | None = None):
        super().__init__(RuleParams(threshold=threshold, softness=softness, direction=direction, range=range), rng)
        self.name = name

    def measure(self, signals: Signals) -> float | None:
        value = signals.get(self.name)
        return None if value is None else float(value)

    def __repr__(self) -> str:
        op = ">=" if self.params.direction > 0 else "<="
        soft = f" ~{self.params.softness:g}" if self.params.softness else ""
        return f"{self.name} {op} {self.params.threshold:g}{soft}"


def is_true(name: str) -> SignalRule:
    return SignalRule(name, threshold=1)


def is_false(name: str) -> SignalRule:
    return SignalRule(name, threshold=0, direction=-1)


@dataclass
class Level:
    rules: list[Rule]
    need: int | None = None  # yes-votes needed; None = a majority

    def approves(self, signals: Signals) -> tuple[bool, list[bool]]:
        votes = [rule.decide(signals) for rule in self.rules]
        need = self.need if self.need is not None else len(self.rules) // 2 + 1
        return sum(votes) >= need, votes


def all_of(*rules: Rule) -> Level:
    return Level(list(rules), need=len(rules))


def majority(*rules: Rule) -> Level:
    return Level(list(rules))


@dataclass
class Pipeline:
    name: str
    levels: list[Level] = field(default_factory=list)
    last: list[tuple[int, list[bool]]] = field(default_factory=list)  # how the last decision went, for debugging

    def decide(self, signals: Signals) -> bool:
        self.last = []
        for number, level in enumerate(self.levels, start=1):
            approved, votes = level.approves(signals)
            self.last.append((number, votes))
            if not approved:
                return False
        return True

    def explain(self) -> str:
        return "; ".join(f"level {n}: {sum(v)}/{len(v)}" for n, v in self.last)
