import random
from datetime import datetime, timedelta, timezone

from proki.legacy.core.meditation import MeditationParams, is_walk, should_suggest, walk_task
from proki.legacy.core.offline import OfflineWork

T0 = datetime(2026, 9, 30, 15, tzinfo=timezone.utc)


def test_suggested_more_often_after_better_sessions():
    rng, p = random.Random(2), MeditationParams()
    assert not any(should_suggest(20, p, rng) for _ in range(100))
    assert 12 < sum(should_suggest(25, p, rng) for _ in range(100)) < 35
    assert 40 < sum(should_suggest(35, p, rng) for _ in range(100)) < 60
    assert sum(should_suggest(50, p, rng) for _ in range(100)) > 75


def test_the_walk_is_offline_work_up_to_its_length():
    walk = walk_task("How should the quota react to sick days?", 30)
    assert is_walk(walk) and walk.offline and not is_walk(None)
    work = OfflineWork()
    assert work.step(walk, T0, T0 + timedelta(minutes=20)).offline  # on the walk: no alarm
    back = work.step(walk, None, T0 + timedelta(minutes=35))
    assert back.back and back.credit == (T0, T0 + timedelta(minutes=35))
