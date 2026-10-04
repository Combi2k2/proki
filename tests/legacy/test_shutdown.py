from datetime import date, datetime, time, timedelta

from proki.legacy.core.offtime import OffTimeParams, near, off_time, often_missed
from proki.legacy.rules.shutdown import LowFocusRule, ShiftContext, TimeRule, shift_ending
from proki.legacy.core.shutdown import ShutdownParams, workday

TUESDAY, SATURDAY = date(2026, 9, 29), date(2026, 10, 3)
P = ShutdownParams()


def local(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute)).astimezone()


def ctx(day, hour, minute=0, intensity=None):
    return ShiftContext(local(day, hour, minute), day, time(4), intensity)


def test_time_rule_is_an_s_curve_around_the_shutdown_time():
    rule = TimeRule(P)
    weight = lambda h, m=0: round(rule.chance(ctx(TUESDAY, h, m)), 2)
    assert weight(16) == 0.01 and weight(17) == 0.1 and weight(17, 30) == 0.25
    assert weight(18) == 0.5 and weight(18, 30) == 0.75 and weight(19) == 0.9
    assert weight(14, 59) == 0  # before its range


def test_low_focus_rule():
    rule = LowFocusRule(P)
    chance = lambda i: round(rule.chance(ctx(TUESDAY, 18, intensity=i)), 2)
    assert chance(None) > 0.98 and chance(0.3) == 0.5 and chance(0.15) == 0.89
    assert chance(0.6) == 0 and chance(0.8) == 0  # focused: never


def test_offer_chance_combines_both():
    rule = shift_ending(P)
    chance = lambda h, m, i: rule.chance(ctx(TUESDAY, h, m, i))
    assert chance(16, 0, None) < 0.02
    assert 0.45 < chance(18, 0, None) < 0.5
    assert chance(18, 30, 0.1) > 0.7  # reading email after 18:00
    assert chance(20, 0, 0.7) == 0  # focused: never


def test_workdays_only_by_default():
    assert workday(TUESDAY, P) and not workday(SATURDAY, P)
    assert shift_ending(P).chance(ctx(SATURDAY, 19)) == 0
    assert not workday(TUESDAY, ShutdownParams(enabled=False))


def test_off_time_is_the_peak_of_long_stops():
    stops = []
    for d in range(7):
        day = TUESDAY - timedelta(days=d)
        stops.append(local(day, 17, 35 + d % 3 * 5))  # 17:35–17:45, most days
    stops += [local(TUESDAY - timedelta(days=d), 23, 50) for d in (1, 3)]  # some nights straight to bed
    assert off_time(stops, time(4)) == time(17, 40)


def test_off_time_around_midnight():
    stops = [local(TUESDAY - timedelta(days=d), 23, 50) for d in range(3)]
    stops += [local(TUESDAY - timedelta(days=d), 0, 10) for d in range(3, 6)]  # after midnight: still late, not early
    assert off_time(stops, time(4)) == time(0, 0)


def test_off_time_needs_enough_days():
    stops = [local(TUESDAY - timedelta(days=d), 17, 40) for d in range(4)]
    assert off_time(stops, time(4)) is None


def test_near_and_often_missed():
    assert near(local(TUESDAY, 17, 20), time(17, 40))
    assert not near(local(TUESDAY, 16, 50), time(17, 40))
    assert not near(local(TUESDAY, 17, 40), None)
    assert often_missed([False, True, False, False, True])
    assert not often_missed([False, True, True, False, True])
