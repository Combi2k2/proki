from datetime import datetime, timedelta, timezone

from proki.legacy.core.backlog import Assessment, Task, ask_if_offline, away_is_offline_work
from proki.legacy.core.offline import OfflineWork

T0 = datetime(2026, 9, 30, 9, 0, tzinfo=timezone.utc)


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def task(offline=True, estimate=40, jev_offline=None) -> Task:
    return Task(1, None, None, "Read chapter 3", "", None, estimate, offline=offline, jev_offline=jev_offline)


def test_asks_only_when_openjev_thinks_it_can_be_done_offline_and_the_user_hasnt_said():
    assert ask_if_offline(task(offline=None, jev_offline=0.8))
    assert not ask_if_offline(task(offline=None, jev_offline=0.2))
    assert not ask_if_offline(task(offline=False, jev_offline=0.9))  # the user said: at the computer


def test_away_counts_as_offline_work_up_to_estimate_plus_grace():
    assert away_is_offline_work(task(), at(0), at(60))
    assert not away_is_offline_work(task(), at(0), at(71))  # 40 min estimate + 30 grace
    assert not away_is_offline_work(task(offline=False), at(0), at(5))
    assert not away_is_offline_work(None, at(0), at(5))


def test_offline_work_is_credited_when_the_user_comes_back():
    work = OfflineWork()
    assert work.step(task(), None, at(0)).offline is False
    for minute in range(3, 30):
        step = work.step(task(), at(2), at(minute))
        assert step.offline and step.away_since is None and step.credit is None  # no alarm, no auto-end
    back = work.step(task(), None, at(30))
    assert back.offline and back.back and back.credit == (at(2), at(30))
    assert work.step(task(), None, at(31)).offline is False  # normal session again


def test_away_far_too_long_credits_the_estimate_then_normal_away_rules():
    work = OfflineWork()
    work.step(task(), at(0), at(10))
    step = work.step(task(), at(0), at(71))
    assert not step.offline and step.credit == (at(0), at(40)) and step.away_since == at(40)


def test_away_during_a_normal_task_is_just_away():
    work = OfflineWork()
    assert work.step(task(offline=False), at(0), at(6)).away_since == at(0)


def test_offline_flag_and_offline_minutes_are_stored(tmp_path):
    from proki.legacy.core.store import Store

    store = Store(tmp_path / "db")
    task_id = store.add_task(None, "Read chapter 3", "", None, 40, T0, assessment=Assessment("deep", 40, 0.9, 0.8))
    assert store.tasks()[0].jev_offline == 0.8 and store.tasks()[0].offline is None
    store.update_task(task_id, offline=1)
    assert store.tasks()[0].offline is True
    assert store.mark_offline_work(at(2) + timedelta(seconds=30), at(30)) == 28  # from the minute the user left
    minutes = store.minutes(at(0), at(60))
    assert {m.activity for m in minutes} == {"offline"} and all(m.intensity == 1.0 for m in minutes)
