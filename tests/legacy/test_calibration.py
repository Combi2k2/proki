import random
from datetime import date, datetime, time, timedelta, timezone

import pytest

from proki.legacy.core.calibration import evaluate, spearman, sweep
from proki.legacy.core.events import Category, Segment
from proki.legacy.focus import FocusParams
from proki.legacy.core.sampling import SamplingParams, SamplingSchedule, plan_day
from proki.legacy.core.store import Store

UTC = timezone.utc
T0 = datetime(2026, 9, 29, 9, 0, tzinfo=UTC)


# --- sampling.py -------------------------------------------------------------

def test_plan_day_stays_in_working_hours_and_keeps_gaps():
    params = SamplingParams(per_day=5, start=time(9), end=time(18), min_gap=timedelta(minutes=45))
    for seed in range(20):
        times = plan_day(date(2026, 9, 29), params, random.Random(seed), UTC)
        assert len(times) == 5
        assert all(time(9) <= t.time() <= time(18) for t in times)
        assert all(b - a >= timedelta(minutes=45) for a, b in zip(times, times[1:]))


def test_plan_day_falls_back_to_even_spacing_when_gaps_cannot_fit():
    params = SamplingParams(per_day=10, start=time(9), end=time(10), min_gap=timedelta(minutes=45))
    times = plan_day(date(2026, 9, 29), params, random.Random(0), UTC)
    assert len(times) == 10 and times == sorted(times)


def test_schedule_fires_once_per_planned_time_and_only_when_present():
    params = SamplingParams(per_day=1, start=time(10), end=time(10, 1), patience=timedelta(minutes=30))
    schedule = SamplingSchedule(params, random.Random(0))
    at_nine = datetime(2026, 9, 29, 9, 0).astimezone()
    assert not schedule.due(at_nine, away=False)  # plans the day, nothing due yet
    at_ten = at_nine + timedelta(hours=1, minutes=5)
    assert not schedule.due(at_ten, away=True)  # due, but the user is away: wait
    assert schedule.due(at_ten + timedelta(minutes=5), away=False)  # back: ask
    assert not schedule.due(at_ten + timedelta(minutes=6), away=False)  # only once


def test_schedule_drops_a_sample_that_waited_too_long():
    params = SamplingParams(per_day=1, start=time(10), end=time(10, 1), patience=timedelta(minutes=30))
    schedule = SamplingSchedule(params, random.Random(0))
    at_nine = datetime(2026, 9, 29, 9, 0).astimezone()
    schedule.due(at_nine, away=False)
    assert not schedule.due(at_nine + timedelta(hours=2), away=False)  # away for the whole window


# --- calibration.py ----------------------------------------------------------

def test_spearman_basics():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert spearman([1, 1, 2, 2], [1, 1, 2, 2]) == pytest.approx(1.0)  # ties handled
    assert spearman([1, 2], [1, 2]) is None  # too few
    assert spearman([1, 2, 3], [5, 5, 5]) is None  # ratings all the same: nothing to rank


def focused_then_scattered() -> tuple[list[Segment], list[tuple[datetime, int]]]:
    """An hour of steady deep work, then an hour of hopping between new sites every 20 s."""
    segments = [Segment(T0, T0 + timedelta(hours=1), "Code", category=Category.DEEP)]
    t = T0 + timedelta(hours=1)
    for i in range(180):
        segments.append(Segment(t, t + timedelta(seconds=20), f"site{i}.com", category=Category.DISTRACTION))
        t += timedelta(seconds=20)
    ratings = [(T0 + timedelta(minutes=m), 5) for m in (20, 35, 50)]
    ratings += [(T0 + timedelta(minutes=m), 1) for m in (80, 95, 110)]
    return segments, ratings


def test_evaluate_finds_agreement_when_the_score_tracks_the_ratings():
    segments, ratings = focused_then_scattered()
    result = evaluate(ratings, segments, FocusParams())
    main = result[FocusParams().main_horizon]
    assert main["intensity"].n == 6
    assert main["intensity"].correlation == pytest.approx(1.0)


def test_sweep_reports_every_candidate_value():
    segments, ratings = focused_then_scattered()
    result = sweep(ratings, segments, FocusParams())
    assert set(result) == {"shallow_weight", "capacity", "dwell_scale_seconds", "main window (minutes)"}
    assert [label for label, _ in result["capacity"]] == ["3", "5", "8"]


# --- store.py ----------------------------------------------------------------

def test_ratings_round_trip_including_skips(tmp_path):
    store = Store(tmp_path / "db")
    store.add_rating(T0, T0 + timedelta(seconds=4), 4, "sampled", {"10m": {"intensity": 0.5}})
    store.add_rating(T0, T0 + timedelta(seconds=9), None, "sampled", {})
    first, skipped = store.ratings()
    assert (first.rating, first.source, first.snapshot["10m"]["intensity"]) == (4, "sampled", 0.5)
    assert skipped.rating is None
