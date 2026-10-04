from datetime import date, datetime, time, timedelta

from proki.legacy.metrics.consistency import consistency

TODAY = date(2026, 9, 30)
DAY_STARTS = time(4)


def start(days_ago: int, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(TODAY - timedelta(days=days_ago), time(hour, minute)).astimezone()


def test_not_enough_days_yet():
    result = consistency({TODAY - timedelta(days=1): start(1, 9)}, TODAY, DAY_STARTS)
    assert result.usual is None


def test_usual_time_is_the_median_and_days_within_30_minutes_count():
    starts = {TODAY - timedelta(days=d): start(d, h, m) for d, h, m in
              [(1, 9, 0), (2, 9, 20), (3, 11, 0), (4, 8, 50), (6, 9, 10)]}  # day 5: no session
    result = consistency(starts, TODAY, DAY_STARTS)
    assert result.usual == time(9, 10)
    assert result.consistent_days == 3  # days 1, 2, 4; day 3 too late, day 5 no session


def test_today_counts_once_it_has_a_session():
    starts = {TODAY - timedelta(days=d): start(d, 9) for d in range(0, 6)}
    assert consistency(starts, TODAY, DAY_STARTS).consistent_days == 5
    del starts[TODAY]
    assert consistency(starts, TODAY, DAY_STARTS).consistent_days == 5  # the 5 days before today


def test_a_start_after_midnight_is_late_not_early():
    # two sessions at 23:30, two just after midnight (00:10, still the same "day" before 04:00)
    starts = {TODAY - timedelta(days=d): start(d, 23, 30) for d in (1, 2)}
    starts.update({TODAY - timedelta(days=d): start(d - 1, 0, 10) for d in (3, 4)})
    assert consistency(starts, TODAY, DAY_STARTS).usual == time(23, 50)  # not 11:50 or 12:00
