from datetime import datetime, timedelta, timezone

from proki.legacy.core.morning import Action, MorningState, State, buffer_for

T0 = datetime(2026, 9, 30, 7, 0, tzinfo=timezone.utc)


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def routine(minutes=30) -> MorningState:
    m = MorningState()
    m.step(at(0), True)
    m.start_routine(at(0), minutes)
    return m


def away(m: MorningState, start: int, end: int) -> list:
    return [a for minute in range(start, end + 1) if (a := m.step(at(minute), False)) is not Action.NONE]


def test_buffer_is_20_percent_clamped_to_5_and_20_minutes():
    assert buffer_for(timedelta(minutes=10)) == timedelta(minutes=5)
    assert buffer_for(timedelta(minutes=50)) == timedelta(minutes=10)
    assert buffer_for(timedelta(minutes=200)) == timedelta(minutes=20)


def test_greets_on_the_first_activity_only():
    m = MorningState()
    assert m.step(at(0), active=False) is Action.NONE
    assert m.step(at(1), active=True) is Action.GREET
    assert m.step(at(2), active=True) is Action.NONE


def test_back_early_is_asked_whether_the_routine_is_finished():
    m = routine()
    assert away(m, 1, 20) == []
    assert m.step(at(21), active=True) is Action.CHECK
    assert m.state is State.CHECKING


def test_a_quick_glance_at_the_laptop_is_not_coming_back():
    m = routine()
    m.step(at(1), active=False)
    assert m.step(at(2), active=True) is Action.NONE  # away only a minute: still in the routine


def test_not_yet_goes_back_to_the_routine_with_one_more_minute_each_time():
    m = routine()  # deadline 7:36
    away(m, 1, 20)
    m.step(at(21), True)
    m.not_yet()
    assert m.deadline == at(37) and m.state is State.ROUTINE
    away(m, 22, 30)
    assert m.step(at(31), True) is Action.CHECK  # back early again: asked again
    m.not_yet()
    assert m.deadline == at(38)
    assert away(m, 32, 37) == []
    assert m.step(at(38), False) is Action.ALARM


def test_finished_but_not_working_waits_for_the_deadline_then_rings():
    m = routine()
    away(m, 1, 20)
    m.step(at(21), True)
    m.finished_not_working()
    assert m.step(at(30), True) is Action.NONE  # no more "finished?" questions
    assert m.step(at(36), True) is Action.ALARM


def test_deadline_without_a_session_rings_even_at_the_computer():
    m = routine(20)  # deadline 7:25
    assert m.step(at(10), True) is Action.NONE
    assert m.step(at(25), True) is Action.ALARM


def test_starting_a_session_ends_the_morning_and_silences_the_alarm():
    m = routine()
    away(m, 1, 36)
    assert m.state is State.RINGING
    assert m.step(at(40), True, in_session=True) is Action.SILENCE
    assert m.step(at(41), True) is Action.NONE


def test_a_session_started_during_the_routine_ends_it_quietly():
    m = routine()
    assert m.step(at(5), True, in_session=True) is Action.NONE
    assert m.state is State.DONE
