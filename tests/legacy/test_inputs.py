from datetime import datetime, timedelta, timezone

from proki.legacy.core.events import Category, Segment
from proki.legacy.focus.depth import depth, mode
from proki.legacy.focus.params import FocusParams
from proki.legacy.focus.window import slice_window
from proki.legacy.core.timeline import attach_inputs, input_actions, merge

T0 = datetime(2026, 10, 1, 10, tzinfo=timezone.utc)
P = FocusParams()


def at(minutes):
    return T0 + timedelta(minutes=minutes)


def test_input_actions_count_half_the_presses():
    assert input_actions({"presses": 40, "clicks": 3, "deltaX": 900}) == 23


def test_segments_get_actions_per_minute():
    seg = Segment(at(0), at(2), "Code", category=Category.DEEP)
    inputs = [(at(0), at(1), 30.0), (at(1), at(2), 10.0), (at(5), at(6), 99.0)]
    assert attach_inputs([seg], inputs)[0].inputs == 20.0
    assert attach_inputs([seg], [])[0].inputs is None  # no input watcher: unknown


def test_merge_keeps_a_time_weighted_rate():
    a = Segment(at(0), at(3), "Code", inputs=30.0)
    b = Segment(at(3), at(4), "Code", inputs=10.0)
    assert merge([a, b])[0].inputs == 25.0


def test_creating_counts_more_than_consuming():
    assert mode(None, P) == 1.0
    assert round(mode(0, P), 2) == 0.82 and round(mode(10, P), 2) == 0.9 and round(mode(30, P), 2) == 1.0
    typing = [Segment(at(0), at(5), "Code", category=Category.DEEP, inputs=30)]
    reading = [Segment(at(0), at(5), "Preview", category=Category.DEEP, inputs=1)]
    social = [Segment(at(0), at(5), "Chrome", url="https://facebook.com/", category=Category.DISTRACTION, inputs=1)]
    score = lambda segs: depth(slice_window(segs, at(5), timedelta(minutes=5)), P)
    assert score(typing) > score(reading) > score(social) == 0
