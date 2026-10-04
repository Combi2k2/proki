from datetime import datetime, timedelta, timezone

import requests

from proki.legacy.config import UNTRACKED, parse
from proki.legacy.core.categories import Categorizer, prepare, unknown
from proki.core.events import Category, Segment
from proki.legacy.core.jev import suggest_category
from proki.services.jev import Jev
from proki.legacy.rules.fragmentation import Fragmentation
from proki.legacy.core.store import Store
from proki.legacy.core.timeline import Tab, build

T0 = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def test_away_time_is_cut_out_and_added_as_its_own_segment():
    windows = [Segment(at(0), at(30), "Code", "proki")]
    segments = build(windows, away=[(at(10), at(20))], tabs=[])
    assert [(s.app, s.start, s.end, s.away) for s in segments] == [
        ("Code", at(0), at(10), False),
        ("(away)", at(10), at(20), True),
        ("Code", at(20), at(30), False),
    ]


def test_browser_segment_gets_the_most_overlapping_tab():
    windows = [Segment(at(0), at(10), "Google Chrome", "Chrome"), Segment(at(10), at(12), "Code")]
    tabs = [
        Tab(at(0), at(2), "https://www.youtube.com/watch?v=1", "Video"),
        Tab(at(2), at(10), "https://github.com/org/repo/pull/1", "PR #1"),
    ]
    chrome, code = build(windows, away=[], tabs=tabs)
    assert chrome.url.startswith("https://github.com") and chrome.title == "PR #1"
    assert chrome.key == "github.com"
    assert code.url is None  # tabs only attach to browsers


def config_with(track, categories):
    return parse({"track": track, "category": categories})


def test_rules_win_then_remembered_answers(tmp_path):
    store = Store(tmp_path / "db")
    config = config_with([], [{"app": "Code", "category": "deep"}])
    categorizer = Categorizer(config.categories, store)
    assert categorizer.categorize(Segment(at(0), at(1), "Code")) is Category.DEEP
    assert categorizer.categorize(Segment(at(0), at(1), "Slack")) is None
    store.set_category("Slack", Category.SHALLOW, "user", T0)
    assert categorizer.categorize(Segment(at(0), at(1), "Slack")) is Category.SHALLOW


def test_untracked_keeps_category_but_loses_name(tmp_path):
    config = config_with(
        track=[{"app": "Code"}],
        categories=[{"app": "Google Chrome", "url": "youtube\\.com", "category": "distraction"}],
    )
    segments = [
        Segment(at(0), at(5), "Code", "main.py"),
        Segment(at(5), at(9), "Google Chrome", "Video", "https://youtube.com/watch"),
    ]
    code, chrome = prepare(segments, config, Categorizer(config.categories, Store(tmp_path / "db")))
    assert code.app == "Code" and code.title == "main.py"
    assert (chrome.app, chrome.title, chrome.url) == (UNTRACKED, "", None)
    assert chrome.category is Category.DISTRACTION


def test_unknown_lists_only_tracked_unclassified_above_threshold():
    segments = [
        Segment(at(0), at(3), "Slack"),
        Segment(at(3), at(4), "Notes"),
        Segment(at(4), at(9), UNTRACKED),
        Segment(at(9), at(12), "Code", category=Category.DEEP),
        Segment(at(12), at(20), "(away)", away=True),
    ]
    assert unknown(segments, timedelta(minutes=2)) == [("Slack", timedelta(minutes=3))]


def test_fragmentation_ignores_away_segments():
    segments = [Segment(at(i / 6), at((i + 1) / 6), "AB"[i % 2]) for i in range(20)]
    segments.append(Segment(at(4), at(9), "(away)", away=True))
    assert Fragmentation(max_switches=25).check(segments, at(9)) is None


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_openjev_suggestion_is_parsed(monkeypatch):
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(json)
        return FakeResponse({"answers": {"category": {
            "type": "choice", "choice": "shallow", "probabilities": {"shallow": 0.8, "deep": 0.2}}}})

    monkeypatch.setattr(requests, "post", fake_post)
    assert suggest_category(Jev("http://jev.test", "key"), "Slack") == (Category.SHALLOW, 0.8)
    assert "Slack" in sent["state"]


def test_openjev_failure_returns_none(monkeypatch):
    def failing_post(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(requests, "post", failing_post)
    assert suggest_category(Jev("http://jev.test", "key"), "Slack") is None


def test_identical_neighbours_merge_across_small_gaps():
    from proki.legacy.core.timeline import merge

    segments = [
        Segment(at(0), at(1), UNTRACKED),
        Segment(at(1), at(2), UNTRACKED),
        Segment(at(2.05), at(3), UNTRACKED),  # 3 s gap
        Segment(at(3), at(4), "Code"),
        Segment(at(5), at(6), "Code"),  # 60 s gap: stays separate
    ]
    assert [(s.app, s.start, s.end) for s in merge(segments)] == [
        (UNTRACKED, at(0), at(3)),
        ("Code", at(3), at(4)),
        ("Code", at(5), at(6)),
    ]


def test_browser_is_only_asked_about_per_website():
    segments = [
        Segment(at(0), at(5), "Google Chrome"),  # no URL: never asked about as a whole
        Segment(at(5), at(9), "Google Chrome", "PR #1", "https://github.com/org/repo/pull/1"),
    ]
    assert unknown(segments, timedelta(minutes=2)) == [("github.com", timedelta(minutes=4))]


def test_browser_internal_pages_are_neutral(tmp_path):
    categorizer = Categorizer([], Store(tmp_path / "db"))
    new_tab = Segment(at(0), at(1), "Google Chrome", "New Tab", "chrome://newtab/")
    assert categorizer.categorize(new_tab) is Category.NEUTRAL
