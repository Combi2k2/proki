from datetime import date, datetime, timedelta, timezone

from proki.core.events import Segment
from proki.legacy.core.experiment import Experiment, SlipWatch, verdict

T0 = datetime(2026, 10, 1, 20, tzinfo=timezone.utc)


def on(url, app="Google Chrome"):
    return Segment(T0, T0, app, "", url)


def test_days_and_when_the_questions_come():
    e = Experiment(1, "instagram.com", date(2026, 10, 1), "running")
    assert e.day(date(2026, 10, 1)) == 1 and e.day(date(2026, 10, 30)) == 30
    assert not e.due(date(2026, 10, 30)) and e.due(date(2026, 10, 31))


def test_two_noes_quit_for_good():
    assert verdict(False, False) == "quit"
    assert verdict(True, False) == verdict(False, True) == "back"


def test_a_slip_is_10_seconds_on_it_counted_once_per_visit():
    watch = SlipWatch()
    insta, other = on("https://www.instagram.com/"), on("https://github.com/")
    step = lambda s, seg: watch.step(T0 + timedelta(seconds=s), seg, "instagram.com")
    assert [step(s, insta) for s in range(0, 10, 2)] == [False] * 5  # a glance
    assert step(10, insta) and not step(12, insta) and not step(30, insta)
    step(32, other)
    assert not step(34, insta) and step(44, insta)  # back again: a new visit, a new slip


def test_grand_gesture_session_rules():
    from proki.legacy.core.grand import grand_session
    from proki.legacy.core.session import SessionParams

    p = grand_session(SessionParams(), 4)
    assert p.wrap_up == timedelta(hours=4) and p.away_alarm_after == timedelta(minutes=20)
    assert p.away_end_after == timedelta(minutes=45) and p.build_up == SessionParams().build_up


def test_sprint_counts_down_and_can_be_extended():
    from proki.legacy.core.sprint import Sprint

    s = Sprint("Draft CV", 10, T0 + timedelta(minutes=25))
    assert s.left(T0) == timedelta(minutes=25) and not s.due(T0)
    assert s.due(T0 + timedelta(minutes=25))
    s.asked = True
    assert not s.due(T0 + timedelta(minutes=26))
    s.extend(T0 + timedelta(minutes=26), 5)
    assert s.due(T0 + timedelta(minutes=31))


def test_hub_and_spoke_reminds_once_per_visit_in_sessions_only():
    from proki.legacy.core.hub import HubWatch

    watch = HubWatch()
    mail = on("https://mail.google.com/")
    step = lambda s, seg=mail, kind="email", session=True: watch.step(T0 + timedelta(seconds=s), seg, kind, session)
    assert not step(0) and not step(10) and step(16) and not step(30)
    step(32, on("https://github.com/"), "code_hosting")
    assert not step(34) and step(50)  # a new visit
    assert not any(step(s, session=False) for s in range(60, 120, 2))  # outside sessions: never
