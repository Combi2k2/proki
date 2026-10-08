from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from conftest import replay
from proki.compiler import compile_config
from proki.core.rules import Rule
from proki.core.primitives import Primitive
from proki.core.signals import Signal, Stream
from proki.errors import RuleError
from proki.services.activitywatch import Event, Record

T0 = datetime(2026, 10, 1, 10, tzinfo=timezone.utc)


def at(minutes):
    return T0 + timedelta(minutes=minutes)


class Value(Stream):
    """A stand-in signal: whatever value the test sets."""

    def __init__(self, name, value=None):
        self.name, self.value = name, value
        Stream.registry[name] = self

    def compute(self):
        return self.value


def chances(rule, *values):
    """The rule's chance with x at each value, a cycle each."""
    out = []
    for i, v in enumerate(values):
        Stream.registry["x"].value = v
        Stream.tick(T0 + i * Stream.cycle)
        out.append(rule.chance())
    return tuple(out)


def test_the_chance_follows_the_comparison():
    Value("x")
    assert chances(Rule("gt", lhs="x", cmp="gt", rhs=3), 2.9, 3, 3.1, None) == (0, 0, 1, 0)
    assert chances(Rule("ge", lhs="x", cmp="ge", rhs=3), 2.9, 3, 3.1) == (0, 1, 1)
    assert chances(Rule("lt", "x", "lt", 3), 2.9, 3) == (1, 0)
    assert chances(Rule("le", "x", "le", 3), 3, 3.1) == (1, 0)
    assert chances(Rule("eq", lhs="x", cmp="eq", rhs=3), 3, 3.1) == (1, 0)
    assert chances(Rule("ne", lhs="x", cmp="ne", rhs=3), 3, 3.1) == (0, 1)
    assert chances(Rule("text", lhs="x", cmp="eq", rhs='"chat"'), "chat", "mail") == (0, 0)  # numbers only
    assert chances(Rule("flag", lhs="x", cmp="eq", rhs=1), True, False) == (1, 0)


def test_softness_makes_it_gradual():
    Value("x")
    assert chances(Rule("soft", lhs="x", cmp="gt", rhs=3, softness=1), 3, 4, 2) == pytest.approx((0.5, 0.731, 0.269), abs=1e-3)
    assert chances(Rule("soft_lt", lhs="x", cmp="lt", rhs=3, softness=1), 2) == pytest.approx((0.731,), abs=1e-3)
    assert chances(Rule("near", lhs="x", cmp="eq", rhs=3, softness=1), 3, 4, 1) == pytest.approx((1, 0.607, 0.135), abs=1e-3)
    assert chances(Rule("far", lhs="x", cmp="ne", rhs=3, softness=1), 3, 4) == pytest.approx((0, 0.393), abs=1e-3)


def test_both_sides_are_expressions():
    Value("x")
    Value("y", 2)
    rule = Rule("over", lhs="x * 2", cmp="gt", rhs="y + 1")
    assert chances(rule, 1, 2) == (0, 1)
    assert "over.lhs" in Stream.registry and rule.lhs.expr == "x * 2"  # its sides, hidden signals


def test_rules_are_checked():
    Value("x")
    for kwargs, problem in [({}, "lhs is missing"), ({"lhs": "x", "cmp": "gt"}, "rhs is missing"),
                            ({"lhs": "x", "rhs": 1}, "has to be one of"), ({"lhs": "x", "cmp": ">", "rhs": 1}, "has to be one of"),
                            ({"lhs": "x", "cmp": "gt", "rhs": 1, "softness": -1}, "negative"),
                            ({"lhs": "y", "cmp": "gt", "rhs": 1}, "unknown name 'y'")]:
        with pytest.raises(ValueError, match=problem):
            Rule("r", **kwargs)


def test_a_rule_reads_its_signals_now_and_is_sampled(tmp_path):
    config = tmp_path / "config.json"
    config.write_text('''{
      "inputs": [{"name": "keys", "backfill": 60}],
      "rules": [{"name": "busy", "lhs": "ts_mean(keys, 2)", "cmp": "gt", "rhs": 30, "softness": 5}]
    }''')
    busy, = compile_config(config).rules
    typing = [Event(at(m / 12), at((m + 1) / 12), {"presses": 5}) for m in range(5 * 12)]  # 30 a minute
    Stream.now = at(0)
    replay(at(5), Record.of(at(0), at(5), {"os.hid.input": typing}))
    assert busy.chance() == pytest.approx(0.5) and Rule.registry["busy"] is busy
    assert "busy" not in Stream.registry  # a rule isn't a signal
    rng = np.random.default_rng(1)
    assert 400 < sum(busy.decide(rng) for _ in range(1000)) < 600


def test_config_rules_are_checked(tmp_path):
    bad = tmp_path / "config.json"
    x = '"signals": [{"name": "x", "expr": "1"}], '
    for text, problem in [('{%s"rules": [{"name": "r", "lhs": "x", "cmp": "gt"}]}' % x, "'r': rhs is missing"),
                          ('{%s"rules": [{"name": "r", "lhs": "x", "cmp": "gt", "rhs": 1, "abov": 1}]}' % x, "unknown abov"),
                          ('{%s"rules": [{"name": "r", "expr": "x > 1"}]}' % x, "unknown expr"),
                          ('{%s"rules": [{"name": "r", "input": "x", "above": 1}]}' % x, "unknown above, input"),
                          ('{"rules": [{"name": "r", "lhs": "nothing", "cmp": "gt", "rhs": 1}]}', "unknown name 'nothing'")]:
        bad.write_text(text)
        Stream.registry.clear()
        Rule.registry.clear()
        with pytest.raises(ValueError, match=problem):
            compile_config(bad)


def test_levels_vote_by_majority_the_highest_first():
    Value("x", 1)
    yes = lambda name, level: Rule(name, lhs="x", cmp="gt", rhs=0, level=level)  # always fires
    no = lambda name, level: Rule(name, lhs="x", cmp="lt", rhs=0, level=level)   # never fires
    Stream.tick(T0)
    assert Rule.vote([yes("a", 2), yes("b", 2), no("c", 2), yes("d", 1)])  # 2 of 3, then 1 of 1
    assert not Rule.vote([yes("a", 2), no("b", 2), yes("d", 1)])           # 1 of 2 isn't a majority
    assert not Rule.vote([yes("a", 2), no("d", 1), no("e", 1), yes("f", 1)])
    band = [Rule("over", lhs="x", cmp="gt", rhs=0.5, level=1), Rule("under", lhs="x", cmp="lt", rhs=2, level=1)]  # 0.5 < x < 2
    Stream.tick(T0 + Stream.cycle)
    assert Rule.vote(band)
    assert Rule.vote([])  # nothing against


def test_softness_is_a_number_and_level_a_whole_one():
    Signal("x", "1")
    for kwargs, problem in [({"softness": "0.1"}, "softness is a number"), ({"softness": True}, "softness is a number"),
                            ({"level": "high"}, "level is a whole number"), ({"level": 1.5}, "level is a whole number")]:
        with pytest.raises(RuleError, match=problem):
            Rule("r", "x", "gt", 0, **kwargs)
