import random
from datetime import datetime, time, timedelta

from proki.legacy.core.jev import classify_activity
from proki.legacy.core.routines import (
    ACTIVITY_CATEGORY, TAXONOMY, Absence, AbsenceTracker, ask_probability, confident_activity, likely_options, overnight,
)

T0 = datetime(2026, 9, 30, 12, 0).astimezone()


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def test_every_activity_has_one_category():
    keys = [key for _, (_, items) in TAXONOMY.items() for key, _ in items]
    assert len(keys) == len(set(keys)) == len(ACTIVITY_CATEGORY)


def test_ask_probability_by_duration():
    assert ask_probability(timedelta(minutes=4)) == 0
    assert ask_probability(timedelta(minutes=10)) == 0.2
    assert ask_probability(timedelta(minutes=45)) == 0.6
    assert ask_probability(timedelta(hours=2)) == 0.8
    assert ask_probability(timedelta(hours=5)) == 0.5


def test_openjev_sure_takes_the_activity_unsure_offers_its_best_guesses():
    assert confident_activity([("meal", 0.91), ("family_friends", 0.07)]) == "meal"
    unsure = [("other", 0.64), ("toilet", 0.32), ("coffee_snack", 0.02), ("nap", 0.0)]
    assert confident_activity(unsure) is None
    assert likely_options(unsure) == ["toilet", "coffee_snack"]  # not 'other', not impossible ones
    assert confident_activity([("toilet", 0.5), ("coffee_snack", 0.4)]) is None
    assert confident_activity(None) is None and likely_options(None) == []


def test_classify_activity_reads_openjevs_answer():
    class FakeOpenjev:
        def ask(self, state, questions):
            assert "lunch with Sam" in state and "other" in questions["activity"]["criteria"]
            return {"activity": {"choice": "meal", "confidence": 0.9,
                                 "probabilities": {"meal": 0.91, "family_friends": 0.07, "bogus": 0.02}}}

    assert classify_activity(FakeOpenjev(), "lunch with Sam") == [("meal", 0.91), ("family_friends", 0.07)]


def test_tracker_reports_an_absence_when_the_user_comes_back():
    tracker = AbsenceTracker()
    assert tracker.step(at(0), True) is None
    for minute in range(1, 30):
        assert tracker.step(at(minute), False) is None
    absence = tracker.step(at(30), True)
    assert absence == Absence(at(0), at(30))


def test_laptop_sleep_is_an_absence_too():
    tracker = AbsenceTracker()
    tracker.step(at(0), True)
    # no calls at all while the Mac sleeps
    assert tracker.step(at(90), True) == Absence(at(0), at(90))


def test_short_breaks_are_not_absences():
    tracker = AbsenceTracker()
    tracker.step(at(0), True)
    tracker.step(at(2), False)
    assert tracker.step(at(4), True) is None


def test_should_ask_follows_the_probability():
    tracker = AbsenceTracker(random.Random(1))
    asked = sum(tracker.should_ask(Absence(at(0), at(40))) for _ in range(1000))
    assert 550 < asked < 650  # about 60%


def test_overnight():
    night = Absence(T0.replace(hour=23, minute=30), T0.replace(hour=7) + timedelta(days=1))
    day = Absence(T0, at(90))
    assert overnight(night, time(22), time(4))
    assert not overnight(day, time(22), time(4))


def test_absences_round_trip(tmp_path):
    from proki.legacy.core.store import Store

    store = Store(tmp_path / "db")
    absence_id = store.add_absence(at(0), at(40), None, "unasked")
    store.set_absence_activity(absence_id, None, "typed", note="lunch with Sam")
    store.set_absence_activity(absence_id, "meal", "jev", confidence=0.91)  # the typed text stays
    ((start, end, activity, source),) = store.absences()
    assert (end - start, activity, source) == (timedelta(minutes=40), "meal", "jev")
    assert store.absence_notes() == [("lunch with Sam", "meal", "jev")]


def test_always_ask_for_trying_it_out():
    tracker = AbsenceTracker(random.Random(1), always_ask=True)
    assert all(tracker.should_ask(Absence(at(0), at(6))) for _ in range(20))


def test_absence_starts_at_the_last_input_not_when_away_was_noticed():
    tracker = AbsenceTracker()
    tracker.step(at(0), True)
    tracker.step(at(1), True)
    tracker.step(at(2), True)  # idle from here, but ActivityWatch still says "active" for 3 minutes
    tracker.step(at(4), True)
    tracker.step(at(5), False, away_since=at(2))  # now marked away, backdated to the last input
    assert tracker.step(at(9), True) == Absence(at(2), at(9))


def test_a_stale_away_period_after_coming_back_is_not_reported_again():
    tracker = AbsenceTracker()
    tracker.step(at(0), True)
    tracker.step(at(5), False, away_since=at(0))
    assert tracker.step(at(10), True) == Absence(at(0), at(10))
    # ActivityWatch still shows the old away period (from minute 0) for a moment
    tracker.step(at(10.5), False, away_since=at(0))
    assert tracker.step(at(11), True) is None  # not the same absence a second time


def test_openjev_can_veto_the_question_when_sure_the_user_stayed():
    from proki.legacy.rules.absence import StillThere

    rule = StillThere(0.7)
    assert rule.decide(0.74) and rule.decide(0.7) and not rule.decide(0.6)


def test_context_for_openjev_has_no_titles():
    from proki.core.events import Category, Segment
    from proki.legacy.flows.routines import RoutinesFlow

    watching = Segment(at(0), at(1), "Google Chrome", "Episode 12 – secret title", "https://www.youtube.com/watch?v=x",
                       category=Category.DISTRACTION)
    text = RoutinesFlow._context(Absence(at(0), at(25)), watching, "Video streaming")
    assert "25 minutes" in text
    assert "youtube.com (a website for video streaming, which the person counts as distraction)" in text
    assert "Episode" not in text and "watch?v" not in text


def test_i_was_here_counts_the_time_at_the_computer(tmp_path):
    from proki.legacy.core.store import Store

    store = Store(tmp_path / "db")
    assert store.mark_present(at(0), at(12), "deep") == 12
    assert {e.activity for e in store.minutes(at(0), at(12))} == {"deep"}
