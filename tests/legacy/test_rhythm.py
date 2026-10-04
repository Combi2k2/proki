from datetime import date, datetime, time, timedelta, timezone

from proki.legacy.metrics.history import DayOutcome, chain_length, deep_minutes
from proki.legacy.core.rhythm import Rhythm
from proki.legacy.core.schedule import BlockReminders, Plan, RhythmParams, block_for
from proki.legacy.metrics.ledger import MinuteEntry
from proki.legacy.core.store import Store
from proki.legacy.ui.board import rhythm_lines

UTC = timezone.utc
MON = date(2026, 9, 28)  # a Monday
PARAMS = RhythmParams()


# --- schedule.py ---------------------------------------------------------------

def test_default_block_on_weekdays_only():
    block = block_for(MON, PARAMS, None, UTC)
    assert block.start == datetime(2026, 9, 28, 9, 0, tzinfo=UTC)
    assert block.end == block.start + timedelta(minutes=90)
    assert block_for(date(2026, 10, 4), PARAMS, None, UTC) is None  # Sunday


def test_a_plan_can_move_the_block_even_on_a_day_off():
    block = block_for(date(2026, 10, 4), PARAMS, Plan(date(2026, 10, 4), time(7, 30)), UTC)
    assert block.start.time() == time(7, 30)


def at(hh, mm):
    return datetime(2026, 9, 28, hh, mm, tzinfo=UTC)


def reminders():
    return BlockReminders(block_for(MON, PARAMS, None, UTC))


def test_block_reminder_at_block_time_once():
    r = reminders()
    assert not r.due(at(8, 59), in_session=False)
    assert r.due(at(9, 0), in_session=False)
    r.shown = True
    assert not r.due(at(9, 1), in_session=False)


def test_snooze_asks_again_after_10_minutes_and_skip_stops_it():
    r = reminders()
    r.shown = True
    r.snooze(at(9, 0))
    assert not r.due(at(9, 5), in_session=False)
    assert r.due(at(9, 10), in_session=False)
    r.skip()
    assert not r.due(at(9, 20), in_session=False)


def test_no_reminder_in_a_session_or_after_the_block():
    r = reminders()
    assert not r.due(at(9, 5), in_session=True)
    assert not r.due(at(10, 31), in_session=False)


# --- history.py ------------------------------------------------------------------

def test_deep_minutes_in_a_session():
    entries = [MinuteEntry(at(9, m), 0.8 if m < 30 else 0.2, "deep") for m in range(45)]
    assert deep_minutes(entries, at(9, 0), at(9, 45), 0.6) == 30


def test_chain_counts_kept_days_and_breaks_on_a_miss():
    days = [MON - timedelta(days=i) for i in range(5)]
    outcomes = [DayOutcome(days[0], kept=False), DayOutcome(days[1], True), DayOutcome(days[2], True),
                DayOutcome(days[3], False), DayOutcome(days[4], True)]
    assert chain_length(outcomes, today=MON) == 2  # today still open; yesterday and the day before kept


def test_chain_includes_today_once_kept_and_breaks_on_a_skip():
    assert chain_length([DayOutcome(MON, True), DayOutcome(MON - timedelta(days=1), True)], MON) == 2
    assert chain_length([DayOutcome(MON, False, skipped=True), DayOutcome(MON - timedelta(days=1), True)], MON) == 0


# --- rhythm.py (with the store) ----------------------------------------------------

def test_a_block_is_kept_with_enough_deep_work_in_a_session(tmp_path):
    store = Store(tmp_path / "db")
    rhythm = Rhythm(store, PARAMS, time(0, 0), deep_threshold=0.6)
    session = store.start_session(at(9, 2))
    store.save_minutes([MinuteEntry(at(9, 2) + timedelta(minutes=m), 0.9, "deep") for m in range(30)])
    store.end_session(session, at(9, 40), {}, "user")
    now = at(12, 0)
    assert rhythm.outcome(MON, UTC, now).kept
    assert rhythm.todays_sessions(now)[0].deep_minutes == 30


def test_plans_round_trip(tmp_path):
    store = Store(tmp_path / "db")
    store.save_plan(MON, time(8, 15), at(21, 30))
    assert store.get_plan(MON) == Plan(MON, time(8, 15))


# --- board.py ----------------------------------------------------------------------

def test_rhythm_lines():
    lines = rhythm_lines(block_for(MON, PARAMS, None, UTC), at(8, 0), chain=3, sessions=[])
    assert lines[0].startswith("Deep-work block today: ")
    assert lines[1] == "Chain: 3 days in a row"
