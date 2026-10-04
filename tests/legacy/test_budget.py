import random
from datetime import datetime, timedelta, timezone

from proki.legacy.core.budget import ShallowBudget, ShallowShare, shallow_share
from proki.legacy.rules.budget import BudgetRule

T0 = datetime(2026, 9, 30, 14, tzinfo=timezone.utc)


def test_share_of_active_time():
    s = shallow_share({"deep": 120, "shallow": 90, "distraction": 30, "neutral": 60, "away": 200})
    assert (s.shallow, s.active, s.share) == (90, 300, 0.3)


def test_chance_is_soft_around_the_limit():
    from proki.legacy.core.budget import BudgetParams

    rule = BudgetRule(BudgetParams())
    chance = lambda share: round(rule.chance(ShallowShare(int(share * 300), 300)), 2)
    assert chance(0.30) == 0.5
    assert chance(0.20) == 0.12 and chance(0.25) == 0.27 and chance(0.35) == 0.73 and chance(0.40) == 0.88
    assert rule.chance(ShallowShare(40, 50)) == 0  # under an hour at the computer: not active


def test_checks_are_spaced_and_sampled():
    budget = ShallowBudget(rng=random.Random(3))
    over = ShallowShare(shallow=120, active=300)  # 40%: 88% per check
    assert not budget.should_prompt(T0, ShallowShare(20, 50))
    results = [budget.should_prompt(T0 + timedelta(minutes=m), over) for m in range(0, 3000)]
    checks = 3000 // 30
    assert 0.75 * checks < sum(results) < 0.97 * checks
