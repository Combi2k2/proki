import random

from proki.legacy.rules.pipeline import Level, Pipeline, SignalRule, all_of, is_false, is_true, majority


def test_signal_rule_reads_a_named_quantity():
    rule = SignalRule("focus_5m", threshold=0.5)
    assert rule.decide({"focus_5m": 0.6}) and not rule.decide({"focus_5m": 0.4})
    assert not rule.decide({})  # unknown → never fires
    assert is_true("x").decide({"x": True}) and is_false("x").decide({"x": False}) and not is_false("x").decide({"x": True})


def test_levels_vote_in_order_and_stop_at_the_first_no():
    p = Pipeline("test", [all_of(is_false("in_session")),
                          majority(SignalRule("a", 1), SignalRule("b", 1), SignalRule("c", 1))])
    assert p.decide({"in_session": False, "a": 1, "b": 1, "c": 0})  # 2 of 3
    assert not p.decide({"in_session": False, "a": 1, "b": 0, "c": 0})
    assert p.last == [(1, [True]), (2, [True, False, False])]
    assert not p.decide({"in_session": True, "a": 1, "b": 1, "c": 1})
    assert len(p.last) == 1  # level 2 never voted


def test_a_level_can_need_a_given_number():
    level = Level([SignalRule("a", 1), SignalRule("b", 1), SignalRule("c", 1)], need=1)
    assert level.approves({"a": 0, "b": 0, "c": 1})[0]


def test_soft_rules_are_sampled_in_a_vote():
    p = Pipeline("soft", [majority(SignalRule("x", threshold=0, softness=1, rng=random.Random(5)))])
    assert 400 < sum(p.decide({"x": 0.0}) for _ in range(1000)) < 600


def test_suggest_a_session_when_focus_builds_up_outside_one():
    from proki.legacy.rules.suggest_session import suggest_session

    p = suggest_session()
    rising = {"in_session": False, "shutdown_done": False, "popup_open": False, "minutes_since_suggested": 999,
              "focus_rise": 0.4, "focus_5m": 0.8, "on_deep": True}
    assert p.decide(rising)
    assert not p.decide({**rising, "in_session": True})
    assert not p.decide({**rising, "focus_rise": -0.2, "focus_5m": 0.1, "on_deep": False})
    assert p.decide({**rising, "focus_5m": 0.1})  # 2 of 3 still a majority
