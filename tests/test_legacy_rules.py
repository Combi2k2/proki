"""The config's rules (config.json) decide like the legacy rule classes they replaced."""
import json
from datetime import date, datetime, time, timedelta, timezone

import pytest

from proki.compiler import CONFIG
from proki.core.rules import Rule
from proki.core.signals import Stream
from proki.legacy.core.shutdown import ShutdownParams
from proki.legacy.rules.base import RuleParams, chance_at
from proki.legacy.rules.shutdown import ShiftContext, shift_ending

SHIPPED = {r["name"]: r for r in json.loads(CONFIG.read_text())["rules"]}
TUESDAY = date(2026, 9, 29)


class Value(Stream):
    def __init__(self, name):
        self.name, self.value = name, None
        Stream.registry[name] = self

    def compute(self):
        return self.value


def rules(*names):
    return [Rule(**SHIPPED[name]) for name in names]


def at(values):
    """Set the stand-in signals and move on a cycle."""
    for name, v in values.items():
        Stream.registry[name].value = v
    Stream.now = (Stream.now or datetime(2026, 9, 29, tzinfo=timezone.utc)) + Stream.cycle
    Stream.tick(Stream.now)


def product(rs):
    p = 1.0
    for r in rs:
        p *= r.chance()
    return p


def test_the_shutdown_offer_has_the_legacy_chance():
    """shift_ending: time of day × low focus, as a product; here one rule a level (each must fire)."""
    for name in ("clock", "focus_5m"):
        Value(name)
    shutdown = rules("shutdown_window", "shutdown_time", "shutdown_not_focused", "shutdown_low_focus")
    legacy = shift_ending(ShutdownParams())
    assert len({r.level for r in shutdown}) == 4  # one a level: a vote is the product
    for hour, minute in [(14, 59), (15, 0), (16, 0), (17, 30), (18, 0), (18, 30), (19, 0), (21, 0)]:
        for focus in (0.0, 0.15, 0.3, 0.45, 0.59, 0.6, 0.8):
            local = datetime.combine(TUESDAY, time(hour, minute)).astimezone()
            at({"clock": hour * 60 + minute, "focus_5m": focus})
            expected = legacy.chance(ShiftContext(local, TUESDAY, time(4), focus))
            assert product(shutdown) == pytest.approx(expected, abs=0.005), (hour, minute, focus)


def test_suggesting_a_session_has_the_legacy_rules():
    for name in ("in_session", "shutdown_done", "popup_open", "since_suggested", "focus_rise", "focus_5m", "depth"):
        Value(name)
    gate = rules("suggest_not_in_session", "suggest_not_shut_down", "suggest_no_popup", "suggest_not_lately")
    votes = rules("focus_rising", "focus_high", "deep_now")
    assert len({r.level for r in gate}) == 4 and {r.level for r in votes} == {1}  # all of, then a majority
    for since in (0, 30, 45, 60, 10_000):
        at({"in_session": False, "shutdown_done": False, "popup_open": False, "since_suggested": since})
        assert gate[3].chance() == pytest.approx(chance_at(since, RuleParams(threshold=45, softness=10)), abs=1e-9)
        assert product(gate[:3]) == 1
    at({"in_session": True})
    assert gate[0].chance() == 0
    for rise, focus, depth in [(0.2, 0.6, 1.0), (0.0, 0.3, 0.25), (0.15, 0.5, None)]:
        at({"focus_rise": rise, "focus_5m": focus, "depth": depth})
        assert votes[0].chance() == pytest.approx(chance_at(rise, RuleParams(threshold=0.15, softness=0.05)))
        assert votes[1].chance() == pytest.approx(chance_at(focus, RuleParams(threshold=0.5, softness=0.1)))
        assert votes[2].chance() == (1 if depth == 1 else 0)


def test_low_focus_in_a_session_is_low_and_not_recovering():
    for name in ("focus_2m", "focus_2m_rise"):
        Value(name)
    low = rules("session_low_focus", "session_not_recovering")
    for focus, rise, expected in [(0.2, 0.0, True), (0.2, 0.1, False), (0.5, 0.0, False), (0.34, 0.05, True)]:
        at({"focus_2m": focus, "focus_2m_rise": rise})
        assert Rule.vote(low) is expected, (focus, rise)
