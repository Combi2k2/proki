"""Tests for proki.legacy.focus, one section per component."""

from datetime import datetime, timedelta, timezone

import pytest

from proki.legacy.config import parse
from proki.core.events import Category, Segment
from proki.legacy.focus import FocusParams, moment, series, summarize
from proki.legacy.focus.continuity import continuity, mean_dwell_seconds
from proki.legacy.focus.depth import depth
from proki.legacy.focus.stability import effective_items, fit, hit_rate
from proki.legacy.focus.window import slice_window

T0 = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)
DEEP, SHALLOW, DISTRACTION, NEUTRAL = Category.DEEP, Category.SHALLOW, Category.DISTRACTION, Category.NEUTRAL
TEN_MIN = timedelta(minutes=10)
PARAMS = FocusParams()


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def seg(start: float, end: float, item: str, category=DEEP) -> Segment:
    return Segment(at(start), at(end), item, category=category)


def rotation(items: list[str], minutes: float, every: float, category=DEEP) -> list[Segment]:
    """Cycle through `items`, switching every `every` minutes, for `minutes`."""
    return [seg(i * every, (i + 1) * every, items[i % len(items)], category) for i in range(int(minutes / every))]


# --- window.py -------------------------------------------------------------

def test_window_clips_stretches_and_ignores_away():
    w = slice_window([seg(0, 8, "Code"), Segment(at(8), at(12), "(away)", away=True), seg(12, 20, "Code")],
                     at(20), TEN_MIN)
    assert [(s.item, s.seconds) for s in w.stretches] == [("Code", 8 * 60)]  # 10–20 minus away 10–12
    assert w.switches == []  # coming back from away is not a switch


def test_window_title_change_on_same_item_is_not_a_switch():
    w = slice_window([Segment(at(0), at(5), "Code", "a.py", category=DEEP),
                      Segment(at(5), at(10), "Code", "b.py", category=DEEP)], at(10), TEN_MIN)
    assert w.switches == [] and len(w.stretches) == 1


def test_window_records_how_long_ago_a_switch_target_was_used():
    w = slice_window([seg(0, 2, "Code"), seg(2, 9, "Chrome · docs"), seg(9, 10, "Code")], at(10), TEN_MIN)
    assert [s.since_last_use for s in w.switches] == [None, timedelta(minutes=7)]


# --- depth.py --------------------------------------------------------------

def test_depth_weights_categories_and_leaves_out_neutral():
    w = slice_window([seg(0, 4, "Code", DEEP), seg(4, 8, "Slack", SHALLOW), seg(8, 10, "Music", NEUTRAL)],
                     at(10), TEN_MIN)
    assert depth(w, PARAMS) == pytest.approx((4 * 1.0 + 4 * 0.3) / 8)


def test_depth_is_undefined_with_only_neutral_time():
    assert depth(slice_window([seg(0, 10, "Finder", NEUTRAL)], at(10), TEN_MIN), PARAMS) is None


def test_depth_shallow_weight_comes_from_config():
    params = parse({"focus": {"shallow_weight": 0.0}}).focus
    assert depth(slice_window([seg(0, 10, "Slack", SHALLOW)], at(10), TEN_MIN), params) == 0.0


# --- stability.py ----------------------------------------------------------

def test_stability_small_rotation_is_all_hits_and_fits():
    w = slice_window(rotation(["Code", "Chrome · docs", "Terminal"], 20, 0.5), at(20), TEN_MIN)
    assert hit_rate(w) == 1.0 and fit(w, PARAMS) == 1.0


def test_stability_drifting_through_new_items_is_all_misses_and_overflows():
    w = slice_window(rotation([f"site{i}.com" for i in range(40)], 20, 0.5), at(20), TEN_MIN)
    assert hit_rate(w) == pytest.approx(1 / 21)  # 20 switches, 0 hits
    assert effective_items(w) == pytest.approx(20) and fit(w, PARAMS) == pytest.approx(5 / 20)


def test_stability_going_back_to_a_distraction_is_never_a_hit():
    segments = rotation(["Code", "youtube.com"], 20, 1)
    segments = [s if s.key == "Code" else Segment(s.start, s.end, s.app, category=DISTRACTION) for s in segments]
    w = slice_window(segments, at(20), TEN_MIN)
    switches_into_code = sum(s.to_item == "Code" for s in w.switches)
    assert hit_rate(w) == pytest.approx((switches_into_code + 1) / (len(w.switches) + 1))


def test_stability_horizon_decides_whether_a_return_is_a_hit():
    segments = [seg(0, 2, "Code"), seg(2, 10, "news.com", DISTRACTION), seg(10, 12, "Code")]
    # 2-min window: only the switch back to Code, last used 8 min ago → a miss
    assert hit_rate(slice_window(segments, at(12), timedelta(minutes=2))) == 0.5
    # 10-min window: into news.com (a miss) and back to Code within 10 min (a hit)
    assert hit_rate(slice_window(segments, at(12), TEN_MIN)) == pytest.approx(2 / 3)


def test_stability_brief_glances_barely_grow_the_working_set():
    segments = [seg(0, 9.9, "Code")] + [seg(9.9 + i * 0.01, 9.9 + (i + 1) * 0.01, f"s{i}.com") for i in range(5)]
    assert effective_items(slice_window(segments, at(10), TEN_MIN)) < 1.2


# --- continuity.py ---------------------------------------------------------

def test_continuity_mean_dwell_is_active_time_over_stretches():
    w = slice_window(rotation(["Code", "Terminal"], 10, 0.5), at(10), TEN_MIN)  # 20 stretches, 19 switches
    assert mean_dwell_seconds(w) == pytest.approx(600 / 20)


@pytest.mark.parametrize("every_seconds, expected", [(5, 0.22), (20, 0.63), (60, 0.95)])
def test_continuity_curve(every_seconds, expected):
    w = slice_window(rotation(["Code", "Terminal"], 10, every_seconds / 60), at(10), TEN_MIN)
    assert continuity(w, PARAMS) == pytest.approx(expected, abs=0.02)


# --- moment.py -------------------------------------------------------------

def test_moment_single_deep_item_is_full_focus():
    assert moment([seg(0, 20, "Code")], at(20), TEN_MIN, PARAMS).intensity == pytest.approx(1.0)


def test_moment_is_the_product_of_its_components():
    m = moment(rotation(["Code", "Slack"], 20, 0.25, SHALLOW), at(20), TEN_MIN, PARAMS)
    assert m.intensity == pytest.approx(m.depth * m.fit * m.hit_rate * m.continuity)


def test_moment_mostly_away_is_undefined():
    segments = [seg(0, 1, "Code"), Segment(at(1), at(10), "(away)", away=True)]
    assert moment(segments, at(10), TEN_MIN, PARAMS).intensity is None


def test_moment_series_is_oldest_first_one_per_step():
    points = series([seg(0, 30, "Code")], at(30), TEN_MIN, timedelta(minutes=5), timedelta(minutes=1), PARAMS)
    assert [p.window.end for p in points] == [at(25 + i) for i in range(6)]


# --- period.py -------------------------------------------------------------

def test_period_counts_deep_minutes_streaks_intrusions_and_coverage():
    segments = [
        seg(-20, 30, "Code"),  # history before the period, then 30 focused minutes
        seg(30, 31, "youtube.com", DISTRACTION),
        seg(31, 40, "Code"),
        Segment(at(40), at(60), "(away)", away=True),
    ]
    p = summarize(segments, at(0), at(60), PARAMS)
    assert p.longest_deep_streak == 31  # minutes 0..30 inclusive, before YouTube drags the score down
    assert p.deep_minutes >= 31
    assert p.intrusions_per_hour == 1.0
    assert p.coverage == pytest.approx(40 / 60)
    assert p.intensities[-1] is None  # the last window is mostly away
