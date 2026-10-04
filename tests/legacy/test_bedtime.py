from datetime import datetime, time, timedelta

from proki.legacy.core.bedtime import Action, BedtimeParams, Phase, WindDown, night_of, phase

P = BedtimeParams()
DAY_STARTS = time(4, 0)


def local(h, m=0, day=29):
    return datetime(2026, 9, day, h, m).astimezone()


def test_phases_through_the_night():
    assert phase(local(21, 59), P, DAY_STARTS) is Phase.DAY
    assert phase(local(22, 0), P, DAY_STARTS) is Phase.WIND_DOWN
    assert phase(local(23, 59), P, DAY_STARTS) is Phase.WIND_DOWN
    assert phase(local(0, 0, day=30), P, DAY_STARTS) is Phase.HARD_STOP
    assert phase(local(3, 59, day=30), P, DAY_STARTS) is Phase.HARD_STOP
    assert phase(local(4, 0, day=30), P, DAY_STARTS) is Phase.DAY


def test_a_hard_stop_before_midnight_works_too():
    early = BedtimeParams(wind_down=time(21, 30), hard_stop=time(23, 0))
    assert phase(local(22, 0), early, DAY_STARTS) is Phase.WIND_DOWN
    assert phase(local(23, 5), early, DAY_STARTS) is Phase.HARD_STOP
    assert phase(local(1, 0, day=30), early, DAY_STARTS) is Phase.HARD_STOP


def test_disabled_means_always_day():
    assert phase(local(23, 0), BedtimeParams(enabled=False), DAY_STARTS) is Phase.DAY


def test_night_belongs_to_the_evening_before():
    assert night_of(local(0, 30, day=30), DAY_STARTS) == local(22).date()


def run(w: WindDown, start: datetime, minutes: int, active=True) -> list:
    return [(m, a) for m in range(minutes + 1) if (a := w.step(start + timedelta(minutes=m), active)) is not Action.NONE]


def test_pokes_every_5_minutes_from_22_00_while_active():
    w = WindDown(P, DAY_STARTS)
    assert run(w, local(22, 0), 15) == [(0, Action.POKE), (5, Action.POKE), (10, Action.POKE), (15, Action.POKE)]


def test_no_pokes_while_away():
    w = WindDown(P, DAY_STARTS)
    assert run(w, local(22, 0), 15, active=False) == []


def test_ten_more_minutes_once_per_night():
    w = WindDown(P, DAY_STARTS)
    w.step(local(22, 0), True)
    assert w.snooze(local(22, 0))
    assert run(w, local(22, 1), 8) == []  # quiet for 10 minutes
    assert w.step(local(22, 10), True) is Action.POKE
    assert not w.snooze(local(22, 10))  # no second snooze tonight


def test_snooze_is_available_again_the_next_night():
    w = WindDown(P, DAY_STARTS)
    w.step(local(22, 0), True)
    w.snooze(local(22, 0))
    w.step(local(22, 0, day=30), True)
    assert w.snooze(local(22, 0, day=30))


def test_alarm_after_midnight_rings_until_inactive_and_again_if_active():
    w = WindDown(P, DAY_STARTS)
    assert w.step(local(0, 0, day=30), True) is Action.ALARM
    assert w.step(local(0, 1, day=30), True) is Action.NONE  # still ringing
    assert w.step(local(0, 2, day=30), False) is Action.SILENCE  # locked / asleep / away
    assert w.step(local(0, 5, day=30), True) is Action.ALARM  # back at it: ring again


def test_alarm_can_be_turned_off():
    w = WindDown(BedtimeParams(alarm=False), DAY_STARTS)
    assert w.step(local(0, 0, day=30), True) is Action.POKE


def test_morning_silences():
    w = WindDown(P, DAY_STARTS)
    w.step(local(3, 59, day=30), True)
    assert w.step(local(4, 0, day=30), True) is Action.SILENCE


def test_sleep_line():
    from proki.legacy.ui.board import sleep_lines

    assert sleep_lines(None, None) == []
    line = sleep_lines(local(0, 37, day=30), local(8, 12, day=30))[0]
    assert line == "Last night: off at 00:37 · up at 08:12"
