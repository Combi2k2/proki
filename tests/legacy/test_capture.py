from datetime import datetime, timedelta, timezone

from proki.legacy.core.capture import CaptureWatch, FollowUps, Source
from proki.core.events import Category, Segment

T0 = datetime(2026, 9, 30, 14, 0, tzinfo=timezone.utc)
SHALLOW, DISTRACTION, DEEP = Category.SHALLOW, Category.DISTRACTION, Category.DEEP


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def on(url: str, app: str = "Google Chrome", title: str = "") -> Segment:
    return Segment(T0, T0, app, title, url)


MAIL, SLACK = on("https://mail.google.com/mail/u/0/#inbox/abc"), on(None, "Slack", "general")
YOUTUBE, INSTA = on("https://www.youtube.com/watch?v=1"), on("https://www.instagram.com/")
CODE = on(None, "Code", "app.py")


def run(watch, seconds, segment, category, in_session=False):
    return [s for t in seconds if (s := watch.step(at(t), segment, category, in_session))]


def test_shallow_asks_after_15_seconds_once_per_visit():
    watch = CaptureWatch()
    assert run(watch, range(0, 14, 2), MAIL, SHALLOW) == []
    asked = run(watch, range(14, 60, 2), MAIL, SHALLOW)
    assert len(asked) == 1 and asked[0].key == "mail.google.com"


def test_a_glance_is_not_a_visit_and_coming_back_is_a_new_one():
    watch = CaptureWatch()
    run(watch, range(0, 10, 2), MAIL, SHALLOW)
    run(watch, range(10, 20, 2), CODE, DEEP)
    assert run(watch, range(20, 30, 2), MAIL, SHALLOW) == []  # 10 s: still under 15
    assert len(run(watch, range(30, 40, 2), MAIL, SHALLOW)) == 1
    run(watch, [40], SLACK, SHALLOW)
    assert len(run(watch, range(42, 80, 2), MAIL, SHALLOW)) == 1  # back after Slack: a new visit


def test_distraction_asks_after_5_minutes_across_sites_once_per_stretch():
    watch = CaptureWatch()
    assert run(watch, range(0, 150, 2), YOUTUBE, DISTRACTION) == []
    asked = run(watch, range(150, 600, 2), INSTA, DISTRACTION)
    assert len(asked) == 1 and asked[0].key == "instagram.com"


def test_a_short_break_from_distraction_doesnt_restart_the_stretch_a_longer_one_does():
    watch = CaptureWatch()
    run(watch, range(0, 200, 2), YOUTUBE, DISTRACTION)
    run(watch, range(200, 230, 2), CODE, DEEP)  # 30 s away from it
    assert len(run(watch, range(230, 310, 2), YOUTUBE, DISTRACTION)) == 1  # 5 min since the stretch began
    run(watch, range(310, 400, 2), CODE, DEEP)  # 90 s: the stretch is over
    assert run(watch, range(400, 600, 2), YOUTUBE, DISTRACTION) == []
    assert len(run(watch, range(600, 720, 2), YOUTUBE, DISTRACTION)) == 1


def test_nothing_during_a_session():
    watch = CaptureWatch()
    assert run(watch, range(0, 600, 2), YOUTUBE, DISTRACTION, in_session=True) == []
    assert run(watch, range(600, 700, 2), MAIL, SHALLOW, in_session=True) == []


def test_source_matches_the_exact_tab_or_window():
    source = Source.of(MAIL)
    assert source.matches(MAIL)
    assert not source.matches(on("https://mail.google.com/mail/u/0/#inbox/other"))
    window = Source.of(SLACK)
    assert window.matches(SLACK) and not window.matches(on(None, "Slack", "random"))


def test_follow_up_after_15_minutes_without_going_back():
    follow = FollowUps()
    tasks = [(7, Source.of(MAIL))]
    assert follow.step(at(0), CODE, tasks) is None
    assert follow.step(at(600), MAIL, tasks) is None  # went back at 10 min
    assert follow.step(at(600 + 899), CODE, tasks) is None
    assert follow.step(at(600 + 900), CODE, tasks) == 7
    follow.not_yet(7, at(1500))
    assert follow.step(at(1600), CODE, tasks) is None
