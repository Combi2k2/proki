from datetime import datetime, timedelta, timezone

from proki.legacy.core.session import Action, BelowThreshold, FocusSession, SessionParams

T0 = datetime(2026, 9, 29, 9, 0, tzinfo=timezone.utc)


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def run(session: FocusSession, start: float, end: float, low: bool, away_since=None, every=0.25) -> list:
    """Step every 15 s from `start` to `end` minutes; return (minute, action) for non-NONE actions."""
    events, t = [], start
    while t <= end + 1e-9:
        action = session.step(at(t), low, away_since)
        if action is not Action.NONE:
            events.append((round(t, 2), action))
        t += every
    return events


def test_focused_session_is_left_alone_until_50_minutes():
    s = FocusSession(T0, SessionParams())
    assert run(s, 0, 49.75, low=False) == []


def test_building_phase_pokes_after_a_minute_of_low_focus_then_every_minute():
    s = FocusSession(T0, SessionParams())
    assert run(s, 5, 8, low=True) == [(6.0, Action.POKE), (7.0, Action.POKE), (8.0, Action.POKE)]


def test_regaining_focus_resets_the_clock():
    s = FocusSession(T0, SessionParams())
    run(s, 5, 5.5, low=True)
    run(s, 5.75, 6, low=False)
    assert run(s, 6.25, 7.25, low=True) == [(7.25, Action.POKE)]  # a full minute low again first


def test_free_phase_asks_if_done_first_then_pokes_if_they_keep_going():
    s = FocusSession(T0, SessionParams())
    assert run(s, 30, 33, low=True) == [(31.0, Action.ASK_DONE), (32.0, Action.POKE), (33.0, Action.POKE)]


def test_free_phase_asks_again_after_the_next_dip():
    s = FocusSession(T0, SessionParams())
    run(s, 30, 31, low=True)  # asked
    run(s, 31.25, 35, low=False)  # focused again
    assert run(s, 35.25, 36.25, low=True)[0] == (36.25, Action.ASK_DONE)


def test_wrap_up_at_50_minutes_then_every_2_minutes_even_when_focused():
    s = FocusSession(T0, SessionParams())
    assert run(s, 49, 56, low=False) == [(50.0, Action.WRAP_UP), (52.0, Action.WRAP_UP),
                                         (54.0, Action.WRAP_UP), (56.0, Action.WRAP_UP)]


def test_alarm_after_5_minutes_away_then_every_minute_until_back():
    s = FocusSession(T0, SessionParams())
    left = at(10)
    assert run(s, 10, 17, low=False, away_since=left) == [(15.0, Action.ALARM), (16.0, Action.ALARM), (17.0, Action.ALARM)]
    assert run(s, 17.25, 18, low=False) == []  # back and focused: quiet


def test_away_10_minutes_ends_the_session():
    s = FocusSession(T0, SessionParams())
    events = run(s, 10, 20, low=False, away_since=at(10))
    assert events[-1] == (20.0, Action.END)
    assert [a for _, a in events[:-1]] == [Action.ALARM] * 5  # minutes 15..19


def test_waking_the_mac_after_hours_ends_the_session_right_away():
    s = FocusSession(T0, SessionParams())
    assert s.step(at(300), low_focus=False, away_since=at(12)) is Action.END


def test_away_time_counts_from_when_the_user_left_not_when_it_was_noticed():
    s = FocusSession(T0, SessionParams())
    # ActivityWatch notices only after 3 minutes; the user actually left at minute 10
    assert run(s, 13, 15, low=False, away_since=at(10))[0] == (15.0, Action.ALARM)


def test_no_pokes_while_away():
    s = FocusSession(T0, SessionParams())
    assert run(s, 5, 9, low=True, away_since=at(5)) == []


def test_counts_are_kept():
    s = FocusSession(T0, SessionParams())
    run(s, 5, 8, low=True)
    assert s.counts[Action.POKE] == 3


def test_below_threshold():
    low = BelowThreshold(0.35)
    assert low(0.2) and not low(0.5) and not low(None)


def test_low_focus_ignores_the_echo_of_a_distraction_while_focus_is_rising():
    from datetime import datetime, timedelta, timezone

    from proki.legacy.rules.focus import LowAndNotRising

    t0 = datetime(2026, 9, 30, 10, tzinfo=timezone.utc)
    low = LowAndNotRising(0.35)
    step = lambda seconds, score: low(score, t0 + timedelta(seconds=seconds))
    assert not step(0, 0.7)
    assert step(15, 0.3)  # dropped to low
    assert step(30, 0.1)  # still falling
    assert step(45, 0.1)  # flat and low
    assert not step(60, 0.2)  # back on task: the 2-min window still echoes the distraction, but it's rising
    assert not step(75, 0.3)
    assert step(120, 0.3)  # stuck low again: flat → low
    assert not step(135, None)
