from datetime import datetime, timedelta, timezone

from proki.legacy.core.association import OPEN, Pair, Contributes, contributions, lifts, pair_minutes
from proki.legacy.core.events import Segment

T0 = datetime(2026, 9, 28, 9, tzinfo=timezone.utc)


def seg(start_m, minutes, key):
    start = T0 + timedelta(minutes=start_m)
    return Segment(start, start + timedelta(minutes=minutes), "Chrome", url=f"https://{key}/")


def test_pairs_come_from_sessions_else_open():
    sessions = [(T0, T0 + timedelta(minutes=60), 1)]
    pairs = pair_minutes([seg(0, 50, "github.com"), seg(50, 30, "github.com"), seg(90, 20, "facebook.com")], sessions)
    assert pairs == {(1, "github.com"): 60, (OPEN, "github.com"): 20, (OPEN, "facebook.com"): 20}


def test_windows_used_for_a_goal_contribute_to_it():
    pairs = {(1, "overleaf.com"): 120, (1, "facebook.com"): 5, (OPEN, "overleaf.com"): 30,
             (OPEN, "facebook.com"): 600, (2, "github.com"): 90, (OPEN, "github.com"): 60}
    result = contributions(pairs)
    assert result == {"overleaf.com": {1}, "github.com": {2}}  # facebook.com contributes to nothing


def test_lift_uses_weighted_minutes_open_counts_a_quarter():
    pairs = {(1, "overleaf.com"): 60, (1, "github.com"): 60, (OPEN, "overleaf.com"): 400, (OPEN, "mail.com"): 1000}
    by_pair = {(p.group, p.window): p.lift for p in lifts(pairs)}
    # weighted: open overleaf 100, open mail 250; total 470; overleaf 160; group 1: 120
    assert round(by_pair[(1, "overleaf.com")], 3) == round((60 / 120) / (160 / 470), 3)
    assert round(by_pair[(1, "github.com")], 3) == round((60 / 120) / (60 / 470), 3)


def test_rule_needs_enough_minutes():
    rule = Contributes()
    assert rule.chance(Pair(1, "x", 3.0, 20)) == 0 and rule.chance(Pair(1, "x", 3.0, 40)) > 0.9
    assert rule.chance(Pair(1, "x", 1.5, 40)) == 0.5
