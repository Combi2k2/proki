import json
from concurrent.futures import Future
from datetime import datetime, timedelta, timezone

import pytest

from proki.legacy.config import parse
from proki.legacy.core.categories import Categorizer
from proki.core.events import Category, Segment
from proki.core.labeling import Labeler, LabelLoop, Question
from proki.core.labels import LabelRegistry, migrate, title_key
from proki.utils import slugify
from proki.legacy.core.store import Store

T0 = datetime(2026, 10, 2, 9, tzinfo=timezone.utc)
CHROME = "Google Chrome"


def at(seconds):
    return T0 + timedelta(seconds=seconds)


class InlineExecutor:
    def __init__(self):
        self.calls = []

    def submit(self, fn, *args):
        self.calls.append(args)
        future = Future()
        future.set_result(fn(*args))
        return future


@pytest.fixture
def registry(tmp_path):
    return LabelRegistry(tmp_path / "labels.json")


def test_slugify():
    assert slugify("Video streaming") == "video_streaming" and slugify("  Lecture videos! ") == "lecture_videos"


def test_the_registry_starts_from_the_taxonomy_and_persists(registry, tmp_path):
    assert registry.category("ide") is Category.DEEP and registry.name("team_chat") == "Chat & messaging"
    slug = registry.add_label("Lecture videos", category=Category.DEEP)
    registry.set(title_key(CHROME, "SLAM lecture - YouTube"), slug, "user", True, T0)
    again = LabelRegistry(tmp_path / "labels.json")
    assert again.label_of(f"{CHROME} · SLAM lecture - YouTube") == "lecture_videos"
    assert again.category("lecture_videos") is Category.DEEP
    assert "lecture_videos" in json.loads((tmp_path / "labels.json").read_text())["labels"]


def test_old_kinds_move_over(registry):
    n = migrate(registry, [("youtube.com", "video_streaming", "user", "x"), ("Slack", "team_chat", "openjev", "x"),
                           ("odd.com", "other", "user", "x")], T0)
    assert n == 2
    assert registry.get("youtube.com").confirmed and not registry.get("Slack").confirmed
    assert registry.get("odd.com") is None  # "something else" has no label


def test_a_similar_title_settles_it_without_asking(registry):
    registry.set(title_key(CHROME, "Inbox (3) - Gmail"), "email", "user", True, T0)
    asked = []
    labeler = Labeler(registry, jev=lambda *a: asked.append(a), gemini=None)
    guess = labeler.similar(CHROME, "Inbox (12) - Gmail")
    assert guess and guess.label == "email"
    assert labeler.similar(CHROME, "Pull requests · proki") is None  # nothing like it
    loop = LabelLoop(labeler, InlineExecutor())
    assert loop.observe(CHROME, "Inbox (12) - Gmail", at(0)) is None
    assert loop.observe(CHROME, "Inbox (12) - Gmail", at(60)) is None and asked == []


def test_a_title_is_compared_within_its_app_or_among_pages(registry):
    registry.set("realpython.com", "education", "user", True, T0)  # a page (from before labels)
    labeler = Labeler(registry, None, None)
    assert labeler.similar("Terminal", "aiwa — uv run python — python3") is None  # not like a website
    guess = labeler.similar(CHROME, "Real Python tutorials")
    assert guess and guess.label == "education"


def test_openjev_then_gemini(registry):
    def labeler(jev, gemini):
        return Labeler(registry, jev=lambda text, labels: jev, gemini=lambda text, labels: gemini)

    assert labeler(("ide", 0.9), "email").suggest("Code", "x.py").source == "openjev"
    unsure = labeler(("ide", 0.4), "email").suggest("Code", "x.py")
    assert (unsure.label, unsure.source) == ("email", "gemini")  # openjev unsure: Gemini
    new = labeler(None, "Lecture videos").suggest(CHROME, "SLAM - YouTube")
    assert new.label == "lecture_videos" and "lecture_videos" in registry.labels  # a new label
    assert labeler(None, None).suggest("Code", "x.py") is None


def test_a_label_from_openjev_is_confirmed_by_you(registry):
    loop = LabelLoop(Labeler(registry, jev=lambda text, labels: ("ide", 0.9), gemini=None), InlineExecutor())
    assert loop.observe("Code", "labels.py — proki", at(0)) is None
    assert loop.observe("Code", "labels.py — proki", at(2)) is None  # asked openjev now
    key = title_key("Code", "labels.py — proki")
    question = loop.observe("Code", "labels.py — proki", at(4))  # its answer is in
    assert registry.get(key).source == "openjev" and not registry.get(key).confirmed
    assert question == Question("confirm", key, "Code", "labels.py — proki")
    loop.answered(question, "ok", at(5))
    assert registry.get(key).confirmed and loop.observe("Code", "labels.py — proki", at(9)) is None


def test_nobody_knows_so_you_are_asked(registry):
    loop = LabelLoop(Labeler(registry, jev=None, gemini=lambda text, labels: None), InlineExecutor())
    loop.observe("Blender", "scene.blend", at(0))
    assert loop.observe("Blender", "scene.blend", at(9)) is None
    question = loop.observe("Blender", "scene.blend", at(10))
    assert question and question.kind == "ask"
    loop.answered(question, "new:3D modelling", at(11))
    assert registry.label_of(question.key) == "3d_modelling" and registry.get(question.key).source == "user"
    assert registry.category("3d_modelling") is None  # the app then asks how it counts


def test_ask_later_and_your_answer_wins(registry):
    loop = LabelLoop(Labeler(registry, jev=lambda text, labels: ("design", 0.9), gemini=None), InlineExecutor())
    loop.observe("Blender", "scene.blend", at(0))
    loop.observe("Blender", "scene.blend", at(2))
    question = loop.observe("Blender", "scene.blend", at(3))
    assert question
    loop.answered(question, "later", at(3))
    assert loop.observe("Blender", "scene.blend", at(60)) is None
    loop.answered(question, "label:writing", at(61))
    assert registry.get(question.key).label == "writing" and registry.get(question.key).source == "user"


def test_categories_come_from_the_label(registry, tmp_path):
    registry.set(title_key("Code", "a.py"), "ide", "user", True, T0)
    store = Store(tmp_path / "db")
    categorizer = Categorizer(parse({}).categories, store, Labeler(registry, None, None))
    code = Segment(T0, T0, "Code", "a.py")
    assert categorizer.kind(code) == "ide" and categorizer.categorize(code) is Category.DEEP
    store.set_category("Code", Category.SHALLOW, "user", T0)  # your answer for that app wins
    assert categorizer.categorize(code) is Category.SHALLOW
