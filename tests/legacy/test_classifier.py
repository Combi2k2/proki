from datetime import datetime, timedelta, timezone

from proki.legacy.config import parse
from proki.legacy.core.classifier import ClassificationLoop, Question
from proki.legacy.core.events import Category, Segment
from proki.legacy.core.store import Store

T0 = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)
CONFIG = {
    "track": [{"app": "Google Chrome"}, {"app": "Notes"}, {"app": "Code"}],
    "category": [{"app": "Code", "category": "deep"}],
}


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def loop(tmp_path):
    return ClassificationLoop(parse(CONFIG), Store(tmp_path / "db"))


def test_untracked_app_gets_a_track_question_after_5_seconds(tmp_path):
    c = loop(tmp_path)
    assert c.observe(Segment(T0, T0, "Blender"), at(0)) is None
    assert c.observe(Segment(T0, T0, "Blender"), at(4)) is None
    assert c.observe(Segment(T0, T0, "Blender"), at(5)) == Question("track", "Blender")


def test_one_answer_tracks_and_classifies_with_no_second_question(tmp_path):
    c = loop(tmp_path)
    c.observe(Segment(T0, T0, "Blender"), at(0))
    c.answered(Question("track", "Blender"), "deep", at(5))
    assert c.config.is_tracked("Blender", "")
    assert c.store.tracked_apps() == ["Blender"]
    assert c.store.get_classification("Blender").category is Category.DEEP
    for t in (6, 30, 120):
        assert c.observe(Segment(T0, T0, "Blender"), at(t)) is None


def test_dont_track_is_remembered_without_the_name(tmp_path):
    c = loop(tmp_path)
    c.answered(Question("track", "Secret App"), "never", at(0))
    c.observe(Segment(T0, T0, "Secret App"), at(1))
    assert c.observe(Segment(T0, T0, "Secret App"), at(60)) is None
    names = c.store._db.execute("SELECT app FROM tracking").fetchall()
    assert names == [(None,)]  # only a hash is stored


def test_no_track_question_for_system_windows_or_partly_tracked_apps(tmp_path):
    config = dict(CONFIG, track=CONFIG["track"] + [{"app": "Safari", "title": "GitHub"}])
    c = ClassificationLoop(parse(config), Store(tmp_path / "db"))
    for segment in [Segment(T0, T0, "loginwindow"), Segment(T0, T0, "Safari", "News")]:
        c.observe(segment, at(0))
        assert c.observe(segment, at(60)) is None


def test_ignore_apps_setting_and_system_windows_are_never_asked_about(tmp_path):
    from datetime import datetime, timedelta, timezone

    from proki.legacy.config import Config
    from proki.legacy.core.classifier import ClassificationLoop
    from proki.legacy.core.events import Segment
    from proki.legacy.core.store import Store

    config = Config(ignore_apps=["Raycast"])
    loop = ClassificationLoop(config, Store(tmp_path / "db"))
    now = datetime.now(timezone.utc)
    for app in ["Raycast", "loginwindow"]:
        assert loop._question_for(Segment(now - timedelta(minutes=1), now, app)) is None
