from datetime import date, datetime, time, timedelta, timezone

import pytest

from proki.core.events import Category, Segment
from proki.legacy.focus import FocusParams
from proki.legacy.metrics.day import day_bounds, summarize_day
from proki.legacy.metrics.keeper import ScoreKeeper
from proki.legacy.metrics.ledger import MinuteEntry, score_minutes
from proki.legacy.core.store import Store
from proki.legacy.ui.board import duration, scoreboard_lines

UTC = timezone.utc
T0 = datetime(2026, 9, 29, 9, 0, tzinfo=UTC)
PARAMS = FocusParams()


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def entry(minute: int, intensity, activity="deep") -> MinuteEntry:
    return MinuteEntry(at(minute), intensity, activity)


# --- ledger.py ---------------------------------------------------------------

def test_one_entry_per_finished_minute_with_its_main_activity():
    segments = [
        Segment(at(-30), at(10), "Code", category=Category.DEEP),
        Segment(at(10), at(10.8), "youtube.com", category=Category.DISTRACTION),
        Segment(at(10.8), at(12), "Code", category=Category.DEEP),
    ]
    entries = score_minutes(segments, at(0), at(12.5), PARAMS)  # the unfinished 12th minute is left out
    assert [e.minute for e in entries] == [at(m) for m in range(12)]
    assert entries[0].intensity == pytest.approx(1.0) and entries[0].activity == "deep"
    assert entries[10].activity == "distraction"  # 48 s of YouTube beats 12 s of Code
    assert entries[11].intensity < 1.0  # the YouTube detour lowers the score


def test_a_long_stretch_that_began_hours_earlier_still_counts():
    segments = [Segment(at(-300), at(20), "Blender", category=Category.DEEP)]  # started 5 h before
    entries = score_minutes(segments, at(0), at(3), PARAMS)
    assert [e.activity for e in entries] == ["deep", "deep", "deep"]
    assert all(e.intensity == pytest.approx(1.0) for e in entries)


def test_minutes_without_any_data_have_no_activity():
    entries = score_minutes([], at(0), at(2), PARAMS)
    assert [(e.intensity, e.activity) for e in entries] == [(None, None), (None, None)]


# --- day.py ------------------------------------------------------------------

def test_day_counts_deep_minutes_and_streaks():
    entries = [entry(m, 0.9) for m in range(5)] + [entry(5, 0.2, "distraction")] + [entry(m, 0.8) for m in (6, 7)]
    day = summarize_day(date(2026, 9, 29), entries, threshold=0.6, goal_minutes=10)
    assert (day.deep_minutes, day.longest_streak, day.current_streak) == (7, 5, 2)
    assert day.goal_progress == 0.7
    assert day.minutes_by_activity == {"deep": 7, "distraction": 1}


def test_a_gap_in_minutes_breaks_a_streak():
    day = summarize_day(date(2026, 9, 29), [entry(0, 0.9), entry(1, 0.9), entry(5, 0.9)], 0.6, 60)
    assert day.longest_streak == 2


def test_threshold_is_applied_when_reading():
    entries = [entry(m, 0.5) for m in range(4)]
    assert summarize_day(date(2026, 9, 29), entries, 0.6, 60).deep_minutes == 0
    assert summarize_day(date(2026, 9, 29), entries, 0.4, 60).deep_minutes == 4


def test_day_starts_at_the_configured_time():
    two_am = datetime(2026, 9, 29, 2, 30).astimezone()
    day, start, _ = day_bounds(two_am, time(4, 0))
    assert day == date(2026, 9, 28) and start.hour == 4 and start.date() == date(2026, 9, 28)


# --- keeper.py ---------------------------------------------------------------

def test_keeper_fills_in_the_day_then_only_adds_new_minutes(tmp_path):
    calls = []

    def load(start, end):
        calls.append((start, end))
        return [Segment(at(-60), at(600), "Code", category=Category.DEEP)]

    day_start = datetime.combine(T0.astimezone().date(), time(0, 0), T0.astimezone().tzinfo)
    keeper = ScoreKeeper(Store(tmp_path / "db"), load, PARAMS, day_starts=time(0, 0))
    now = day_start + timedelta(hours=10, seconds=30)
    assert keeper.update(now) == 600  # every minute since the day began
    assert keeper.update(now + timedelta(seconds=20)) == 0  # nothing new finished yet
    assert keeper.update(now + timedelta(minutes=1)) == 1
    assert calls[-1][0] == day_start + timedelta(minutes=600) - 2 * PARAMS.main_horizon  # only what's needed


# --- ui/board.py ---------------------------------------------------------------

def test_scoreboard_lines():
    day = summarize_day(date(2026, 9, 29), [entry(m, 0.9) for m in range(75)], 0.6, 60)
    lines = scoreboard_lines(day, 0.6)
    assert lines[0] == "Today: 75 min of deep work (focus ≥ 0.6)"
    assert "100%" in lines[2] and "▓" * 10 in lines[2]
    assert lines[3] == "Time on: Deep 1h 15m"
    assert duration(59) == "59m" and duration(125) == "2h 05m"


def test_minutes_saved_in_any_time_zone_are_found_by_time(tmp_path):
    from datetime import timezone as tz

    store = Store(tmp_path / "db")
    plus_two = tz(timedelta(hours=2))
    # 03:30 local (+02:00) is 01:30 UTC: before a day starting at 04:00 local
    store.save_minutes([MinuteEntry(datetime(2026, 9, 29, 3, 30, tzinfo=plus_two), 0.9, "deep"),
                        MinuteEntry(datetime(2026, 9, 29, 4, 30, tzinfo=plus_two), 0.9, "deep")])
    day_start = datetime(2026, 9, 29, 4, 0, tzinfo=plus_two)
    found = store.minutes(day_start, day_start + timedelta(days=1))
    assert [e.minute.astimezone(plus_two).hour for e in found] == [4]
