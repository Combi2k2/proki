import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from proki.core.programs import Program
from proki.core.signals import Expr, Stream
from proki.errors import VariableError
from proki.programs.code import classify as module
from proki.programs.code.classify import DEPTH, SHIPPED, AppDB, Apps, Depth, Track, key_of, tokens

NOW = datetime(2026, 10, 15, 10, tzinfo=timezone.utc)


def apps(db=None):
    return Apps(AppDB(db or sqlite3.connect(":memory:")))


@pytest.fixture
def track(monkeypatch):
    """The track space on apps of its own, and `focus_on(window, seconds)`: `window` (app, url) in
    focus at NOW + `seconds`."""
    space = Track(apps())
    space.make()

    def look(window, seconds):
        monkeypatch.setattr(module, "watch", lambda: window)
        monkeypatch.setattr(Program, "now", NOW + timedelta(seconds=seconds))
        Stream.registry["track"].advance(Program.now)  # a cycle: what's in focus, looked at
        return space

    space.focus_on = look
    return space


def read(name):
    return Stream.registry[name].current()


def test_an_app_by_its_name_a_website_by_its_host():
    assert key_of("Code", None) == "Code"
    assert key_of("Google Chrome", "https://www.facebook.com/jdfgsgdiyysid?x=1") == "facebook.com"
    assert key_of("Google Chrome", "https://mail.google.com/mail/u/0/#inbox") == "mail.google.com"
    assert key_of("Google Chrome", "http://localhost:3000/app") == "localhost"
    assert key_of("Google Chrome", "chrome://newtab/") is None  # not a web page: nothing to label
    assert key_of("Google Chrome", None) is None


def test_a_name_is_compared_token_by_token():
    assert tokens("mail.google.com") == ["mail", "google", "com"]
    assert tokens("Visual Studio Code") == ["visual", "studio", "code"]
    assert tokens("animevietsub.nl") == ["anime", "viet", "sub", "nl"]


def test_each_label_has_a_name_of_its_own_and_says_what_it_is():
    names = [label["name"] for label in SHIPPED["labels"]]
    assert len(names) == len(set(names)) and all(label["desc"] for label in SHIPPED["labels"])


def test_a_website_like_one_you_labeled_takes_its_label():
    known = apps()
    known.keep("vimeo.com", NOW, label=known.named("Videos"), source="usr")
    assert known.label("Google Chrome", "https://player.vimeo.com/video/1") == "Videos"
    assert known.label("Google Chrome", "https://www.vimeo.com/channels") == "Videos"  # its own host
    assert known.label("Google Chrome", "https://example.org") is None
    assert known.depth("Google Chrome", "https://vimeo.com") == 0


def test_your_answers_are_kept():
    db = sqlite3.connect(":memory:")
    (known := apps(db)).keep("vimeo.com", NOW, label=known.named("Videos"), source="usr")
    assert apps(db).get("vimeo.com").confirmed and apps(db).get("vimeo.com").set_at == NOW


def test_well_known_apps_come_labeled_for_you_to_confirm():
    known = apps()
    assert known.label("Google Chrome", "https://www.youtube.com/watch") == "Videos"
    assert known.get("youtube.com").source == "dev" and not known.get("youtube.com").confirmed


# --- the track space ------------------------------------------------------------------------

def test_whats_in_focus_and_for_how_long(track):
    track.focus_on(("Krita", None), 0)
    assert (read("track.now")["key"], read("track.since")) == ("Krita", 0)
    track.focus_on(("Krita", None), 59)
    assert read("track.since") == pytest.approx(59 / 60)
    track.focus_on(("Quillpad", None), 60)  # away from it: the minute starts again
    track.focus_on(("Krita", None), 61)
    track.focus_on(("Krita", None), 121)
    assert read("track.since") == 1
    track.focus_on(None, 151)  # away, or proki's window
    assert read("track.now") is read("track.since") is None


def test_each_website_on_its_own_never_the_browser(track):
    track.focus_on(("Google Chrome", "https://www.krita.org/en/download"), 0)
    assert read("track.now")["key"] == "krita.org"
    track.focus_on(("Google Chrome", "chrome://newtab/"), 1)
    assert read("track.now") is None  # a browser on no web page: nothing to label


def test_prokis_windows_and_the_systems_are_never_in_focus():
    class Value(Stream):
        def __init__(self, name, value):
            self.name, self.value = name, value
            Stream.registry[name] = self

        def compute(self):
            return self.value

    def watching(app, title):
        for name, value in {"active": True, "tab_url": None, "app_name": app, "app_title": title}.items():  Value(name, value)
        return module.watch()

    assert watching("proki", "proki question") is None and watching("proki", "proki") is None
    assert watching("proki.exe", "proki question") is None
    assert watching("proki-ui.exe", "proki") is None
    assert watching("Krita", "proki") == ("Krita", None)  # another app's window of that name


def test_every_app_seen_is_kept_tracked_or_not(track):
    track.apps.keep("Krita", NOW, track=False)
    track.focus_on(("Krita", None), 0)
    assert read("track.now") | {"set_at": None} == {"key": "Krita", "track": False, "label": None, "source": "usr", "set_at": None, "conf": None}
    track.focus_on(("Quillpad", None), 1)  # seen the first time: never answered for
    assert read("track.now")["track"] is None and {"Krita", "Quillpad"} <= {app["key"] for app in read("track.all")}
    assert read("track") == {name: read(f"track.{name}") for name in ("labels", "all", "now", "pin", "since", "depth", "reask")}


def test_its_label_by_name_its_depth_a_similar_ones(track):
    track.focus_on(("Google Chrome", "https://www.youtube.com/watch"), 0)
    assert (read("track.now")["label"], read("track.now")["source"], read("track.depth")) == ("Videos", "dev", 0)
    track.apps.keep("vimeo.com", NOW, label=track.apps.named("Videos"), source="usr")
    track.focus_on(("Google Chrome", "https://player.vimeo.com/video/1"), 1)
    assert read("track.now")["label"] is None and read("track.depth") == 0  # none given: the most similar's depth
    assert ["Design", track.apps.known()[track.apps.named("Design")].desc] in Expr("zip(track.labels.name, track.labels.desc)").value()


def test_what_the_config_sets_is_kept(track):
    track.focus_on(("Krita", None), 0)
    now = Stream.registry["track.now"]
    now.set(read("track.now") | {"track": True, "label": "Design"})  # yours
    assert track.apps.get("Krita").confirmed and track.apps.get("Krita").label == track.apps.named("Design")
    now.set(read("track.now") | {"label": "Videos", "source": "jev", "conf": 0.9})  # as jev's
    assert (read("track.now")["label"], read("track.now")["source"], read("track.now")["conf"]) == ("Videos", "jev", 0.9)
    with pytest.raises(VariableError):  now.set(read("track.now") | {"label": "Nothing like it"})
    with pytest.raises(VariableError):  now.set(read("track.now") | {"key": "Quillpad"})
    Stream.registry["track.reask"].set(100)
    assert read("track.reask") == 100
    track.focus_on(("Quillpad", None), 1)
    assert read("track.reask") == 0  # each app's own


def test_labels_are_yours_to_change(track):
    labels = Stream.registry["track.labels"]
    track.focus_on(("Krita", None), 0)
    Stream.registry["track.now"].set(read("track.now") | {"label": "Design"})
    design = track.apps.named("Design")
    labels.set([{**row, "name": "Drawing"} if row["id"] == design else row for row in read("track.labels")])  # renamed
    assert read("track.now")["label"] == "Drawing" and "Drawing" in Expr("track.labels.name").value()
    labels.set([*read("track.labels"), {"name": "Reading", "desc": "Books and papers", "depth": "deep"}])  # a new one, its group and depth from their defaults
    Stream.registry["track.now"].set(read("track.now") | {"label": "Reading"})
    assert read("track.now")["label"] == "Reading" and read("track.depth") == DEPTH[Depth.DEEP]
    labels.set([row for row in read("track.labels") if row["name"] != "Reading"])  # gone: not labeled
    assert read("track.now")["label"] is None


def test_one_pinned_is_read_whatever_is_in_focus(track):
    track.focus_on(("Krita", None), 0)
    Stream.registry["track.pin"].set(read("track.now"))
    track.focus_on(("Quillpad", None), 30)
    assert read("track.pin")["key"] == "Krita" and read("track.now")["key"] == "Quillpad" and read("track.since") == 0  # Quillpad's
    Stream.registry["track.pin"].set(read("track.pin") | {"track": False})
    assert track.apps.get("Krita").track is False and track.apps.get("Quillpad").track is None
    Stream.registry["track.pin"].set(None)
    assert read("track.pin") is None and read("track.since") == pytest.approx(0)


def test_tracking_reads_fresh_activity_after_streams_advance(track, monkeypatch):
    # track is registered first, as in production; its inputs still hold last cycle's
    # values when track.advance runs. Program.now also still refers to that cycle.
    from proki.core.signals import Signal, Variable

    app = Variable("app_name", None)
    active = Variable("has_input", False)
    Signal("active", "has_input")
    Variable("tab_url", None)
    monkeypatch.setattr(Program, "now", NOW)
    Stream.tick(NOW)
    assert read("track.now") is None
    app.set("Quillpad")
    active.set(True)
    for seconds in (10, 20, 30, 40, 50, 60, 70):
        at = NOW + timedelta(seconds=seconds)
        Stream.tick(at)
        Program.now = at
        assert read("track.now")["key"] == "Quillpad"
        assert read("track.since") == pytest.approx((seconds - 10) / 60)
    assert Expr("track.now.track is None and track.since >= 1").value() is True


def test_dwell_uses_the_cycle_clock_even_before_programs_tick(track, monkeypatch):
    monkeypatch.setattr(module, "watch", lambda: ("Quillpad", None))
    monkeypatch.setattr(Program, "now", NOW)
    for seconds in (0, 10, 20, 30, 40, 50, 60):
        at = NOW + timedelta(seconds=seconds)
        Stream.tick(at)
        assert read("track.since") == pytest.approx(seconds / 60)
        Program.now = at
