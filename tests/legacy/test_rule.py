import random
from datetime import datetime, timedelta, timezone

from proki.legacy.rules.base import AllOf, Cadence, Rule, RuleParams, chance_at


def test_soft_threshold_is_50_percent_at_the_line():
    p = RuleParams(threshold=10, softness=2)
    assert chance_at(10, p) == 0.5
    assert round(chance_at(12, p), 2) == 0.73 and round(chance_at(8, p), 2) == 0.27
    assert chance_at(None, p) == 0


def test_direction_below():
    p = RuleParams(threshold=0.35, softness=0.05, direction=-1)
    assert chance_at(0.2, p) > 0.9 and chance_at(0.5, p) < 0.1


def test_hard_rule_fires_from_the_threshold_on():
    p = RuleParams(threshold=5)
    assert (chance_at(4.9, p), chance_at(5, p), chance_at(60, p)) == (0, 1, 1)
    below = RuleParams(threshold=0.35, direction=-1)
    assert (chance_at(0.34, below), chance_at(0.36, below)) == (1, 0)


def test_range_limits_where_the_rule_is_active():
    p = RuleParams(threshold=0, softness=30, range=(-120, None))
    assert chance_at(-121, p) == 0 and chance_at(-60, p) > 0


def test_steps_for_exact_chances():
    p = RuleParams(threshold=5, steps=((5, 0.2), (20, 0.6), (60, 0.8), (180, 0.5)))
    assert [chance_at(v, p) for v in (4, 5, 30, 90, 200)] == [0, 0.2, 0.6, 0.8, 0.5]


class Value(Rule[float]):
    def measure(self, context: float) -> float:
        return context


def test_decide_samples_the_chance():
    rule = Value(RuleParams(threshold=0, softness=1), rng=random.Random(4))
    fired = sum(rule.decide(0.0) for _ in range(2000))
    assert 900 < fired < 1100
    hard = Value(RuleParams(threshold=0))
    assert all(hard.decide(1.0) for _ in range(50)) and not any(hard.decide(-1.0) for _ in range(50))


def test_all_of_multiplies_chances():
    both = AllOf(Value(RuleParams(threshold=0, softness=1)), Value(RuleParams(threshold=0, softness=1)))
    assert both.chance(0.0) == 0.25


def test_cadence_spaces_checks():
    t0 = datetime(2026, 9, 30, tzinfo=timezone.utc)
    cadence = Cadence(timedelta(minutes=15))
    assert cadence.due(t0) and not cadence.due(t0 + timedelta(minutes=10)) and cadence.due(t0 + timedelta(minutes=15))
