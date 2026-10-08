from datetime import datetime, timedelta, timezone

import pytest

from conftest import replay
from proki.services.activitywatch import Event, Record
from proki.core.primitives import App, Label, Primitive, Recording
from proki.core.signals import Signal, Stream, compile_expr
from proki.errors import ExprError
from proki.core.ops import (
    Constant,
    Delay,
    Every,
    Lift,
    TsCount,
    TsMax,
    TsMean,
    TsMin,
    TsRank,
    TsSum,
)

T0 = datetime(2026, 10, 1, 10, tzinfo=timezone.utc)


def at(minutes):
    return T0 + timedelta(minutes=minutes)


class Seq(Stream):
    """A test stream: the next value of a list each cycle."""

    def __init__(self, values):
        self.values = iter(values)

    def advance(self, t):
        super().advance(t)
        self.next = next(self.values)

    def compute(self):
        return self.next


def feed(op, n):
    """`op`'s value over `n` cycles, every 10 s from T0 (on the hour, so spans line up)."""
    out = []
    for i in range(n):
        Stream.tick(T0 + i * Stream.cycle, [op])
        out.append(op.current())
    return out


def test_lift_is_unknown_where_an_input_is():
    assert feed(Lift(lambda a, b: a + b, Seq([1, 2, None]), Seq([10, 20, 30])), 3) == [11, 22, None]
    assert feed(Lift(lambda a, b: a * b, Seq([1, 2]), 3), 2) == [3, 6]


def test_delay_shifts_by_time():
    assert feed(Delay(Seq(range(1, 7)), 0.5), 6) == [None, None, None, 1, 2, 3]  # 30 s: 3 cycles


def test_windows_hold_the_last_w_minutes():
    keys = [30] * 6 + [60] * 6 + [None] * 3  # presses per minute: a minute of each, then 30 s unknown
    assert feed(TsSum(Seq(keys), 2), 15)[-1] == pytest.approx((30 * 3 + 60 * 6) / 6)  # the last 12 cycles: 9 known
    assert feed(TsMean(Seq(keys), 2), 15)[-1] == pytest.approx((30 * 3 + 60 * 6) / 9)  # over the known values
    assert feed(TsMax(Seq(keys), 1), 15)[-1] == 60 and feed(TsMin(Seq(keys), 1), 12)[-1] == 60
    assert feed(TsMean(Seq([None] * 6), 1), 6)[-1] is None
    assert feed(TsSum(Seq([True] * 12), 1), 12)[-1] == pytest.approx(1)  # true for a minute


def test_ts_count_counts_entries():
    on = [False, True, True, False, True, False, False]
    assert feed(TsCount(Seq(on), 7 / 6), 7)[-1] == 2
    assert feed(TsCount(Seq(on), 3 / 6), 7)[-1] == 1  # the last 3 cycles


def test_nesting():
    keys = Seq([10] * 30 + [40] * 30)
    rise = Lift(lambda a, b: a - b, TsMean(keys, 2), Delay(TsMean(keys, 2), 5))
    assert feed(rise, 60)[-1] == pytest.approx(30)


def test_constants():
    assert feed(Constant(3), 1) == [3]


def window(a, b, app, title=""):
    return Event(at(a), at(b), {"app": app, "title": title})


RECORDED = {
    "currentwindow": [window(0, 3, "Code"), window(4, 6, "Google Chrome", "Video"), window(6, 10, "Code")],
    "web.tab.current": [Event(at(4), at(4.1), {"url": "https://www.youtube.com/watch", "title": "Video"})],
    "os.hid.input": [Event(at(m), at(m + 1), {"presses": 40, "clicks": 5, "deltaX": 200, "deltaY": -100})
                     for m in range(10)],
}
KINDS = {"Code": "code_editor", "Video": "video_streaming"}  # by app, or by title (a page)


def kind_of(app, title):
    return KINDS.get(title) or KINDS.get(app)


def primitives(classify):
    """Every primitive, each keeping its last day (as the shipped config does)."""
    Label.label_of = classify
    return [kind(backfill=True, window=timedelta(days=1)) for kind in Primitive.kinds.values()]


def run_to(minutes=10.0):
    Stream.now = at(0)  # cycles from minute 0 (as if the last run ended there)
    replay(at(minutes), Record.of(at(0), at(minutes), RECORDED))


def value(expr):
    primitives(kind_of)
    x = Signal("x", expr)
    run_to()
    return x.current()


def test_primitives_read_the_recording_at_the_cycle():
    signals = primitives(kind_of)
    run_to(10)
    values = {signal.name: signal.current() for signal in signals}
    assert (values["app"], values["title"], values["url"], values["label"]) == ("Code", "", None, "code_editor")
    run_to(5)
    values = {signal.name: signal.current() for signal in signals}
    assert (values["app"], values["url"], values["label"]) == ("Google Chrome", "https://www.youtube.com/watch",
                                                                 "video_streaming")  # the tab, held since 4:00
    assert (values["keys"], values["mouse_click"], values["mouse_move"]) == (20, 5, 300)
    run_to(3.5)
    app = next(s for s in signals if s.name == "app")
    assert app.current() is None  # 30 s after Code's last event


def test_values_hold_over_small_gaps_but_not_long_ones():
    beats = Record.of(at(0), at(3), {"currentwindow": [Event(at(0), at(1), {"app": "Code"}),
                                                          Event(at(1.02), at(2), {"app": "Code"})]})
    app = App("app", "app")
    Recording.rec = beats
    assert app.read(at(1.01)) == "Code" and app.read(at(2.2)) == "Code"  # a 1 s gap; 12 s after
    assert app.read(at(2.5)) is None  # 30 s: the watcher stopped


def test_runs_continue_where_they_left_off():
    primitives(kind_of)
    x = Signal("x", "ts_sum(keys, 10)")
    run_to(4)
    replay(at(10), Record.of(at(0), at(10), RECORDED))
    assert x.current() == pytest.approx(200)  # 20 a minute, from 0:10 to 10:00 (59 cycles + the first)


def test_expressions_on_primitives():
    # a cycle every 10 s from 0:10 to 10:00; Code held 15 s past 3:00 (until 3:10's cycle)
    assert value('ts_sum(label == "code_editor", 10)') == pytest.approx((19 + 24) / 6)
    assert value('ts_sum(app == "Google Chrome", 10)') == pytest.approx(2)
    assert value('ts_count(app, 10)') == 2  # Chrome, Code (the first app known isn't a change)
    assert value('ts_count(label == "video_streaming", 10)') == 1
    assert value('ts_sum(title == "Video", 10)') == pytest.approx(2) and value("url") is None  # Code has no url
    assert value("ts_mean(keys + mouse_click, 5)") == pytest.approx(25)
    assert value("ts_sum(mouse_move, 2)") == pytest.approx(600)
    Signal("in_session", "False")  # any signal can be named
    assert value("ts_mean(keys, 0.5) > 10 and not in_session") is True


def test_expressions_read_other_signals():
    primitives(kind_of)
    Signal("keys_2m", "ts_mean(keys, 2)")
    assert value("keys_2m - delay(keys_2m, 2)") == pytest.approx(0)  # steady typing


def test_signals_need_a_name_and_an_expr():
    for name, expr in (("", "keys"), ("x", "")):
        with pytest.raises(ValueError):
            Signal(name, expr)


def test_expressions_reject_anything_else():
    assert value("2 * 3") == 6
    for bad in ("__import__('os')", "keys.real", "[1, 2]", "nope + 1", "ts_mean(keys"):
        with pytest.raises(ExprError):
            value(bad)


def test_monotonic_queues_keep_ties():
    assert feed(TsMax(Seq([3, 1, 3, 2, 1, 1]), 2 / 6), 6) == [3, 3, 3, 3, 2, 1]
    assert feed(TsMin(Seq([1, None, 2, 0, 5]), 2 / 6), 5) == [1, 1, 2, 0, 0]


def test_signals_reading_each_other_in_a_loop_fail():
    Signal("a", "b + 1")
    Signal("b", "a + 1")
    with pytest.raises(ExprError):
        Stream.tick(T0)


class FakeServer:
    """Answers like an ActivityWatch server that only returns events starting in the range."""

    def __init__(self, events):
        self.stored = events  # bucket type → [Event]
        self.asked = []

    def buckets(self):
        return {f"{kind}_host": {"type": kind} for kind in self.stored}

    def events(self, bucket_id, start=None, end=None, limit=None):
        self.asked.append((bucket_id, start, limit))
        found = [e for e in self.stored[bucket_id.removesuffix("_host")]
                 if (start is None or e.start >= start) and (end is None or e.start <= end)]
        found = sorted(found, key=lambda e: e.start, reverse=True)[:limit]
        return [{"timestamp": e.start.isoformat(), "duration": (e.end - e.start).total_seconds(), "data": e.data}
                for e in found]


def test_fetches_keep_events_that_started_before_the_range():
    server = FakeServer({"currentwindow": [window(0, 30, "Code")],  # one long event, still running
                         "web.tab.current": [Event(at(1), at(1.1), {"url": "https://a.com/"})]})
    first = Record.fetch(at(0), at(29), server)  # type: ignore[arg-type]
    code, tab = first["currentwindow"].covering(at(28.5)), first["web.tab.current"].latest(at(28.5))
    assert code and tab and tab.data["url"] == "https://a.com/"  # the tab, 27 min old
    server.asked.clear()
    later = Record.fetch(at(29), at(31), server, first)  # type: ignore[arg-type]
    code, tab = later["currentwindow"].covering(at(30)), later["web.tab.current"].latest(at(30))
    assert code and code.data["app"] == "Code" and tab  # both started before 29:00
    assert sorted(start for _, start, _ in server.asked) == [at(0), at(1)]  # from each one's newest event


def test_a_fetch_lets_the_previous_record_go():
    server = FakeServer({"currentwindow": [window(0, 30, "Code")]})
    first = Record.fetch(at(0), at(29), server)  # type: ignore[arg-type]
    first["currentwindow"]
    later = Record.fetch(at(29), at(31), server, first)  # type: ignore[arg-type]
    later["currentwindow"]
    assert first.newest == later.newest and all(cell is None or cell.cell_contents is not first
                                                 for cell in (later._fetch.__closure__ or ()))


def test_the_first_run_replays_the_last_day():
    signals = {p.name: p for p in primitives(kind_of)}
    x = Signal("x", "ts_sum(keys, 10)")
    replay(at(10), Record.of(at(-1440), at(10), RECORDED))  # starts a day back
    assert x.current() == pytest.approx(200)  # the whole window, right away
    table = signals["app"].history(at(-1440))
    assert len(table) == 1440 * 6 and table[-1] == (at(10), "Code")  # a day of rows, kept
    assert signals["recorded"].history(at(-60))[0][1] is False  # nothing recorded an hour ago
    assert signals["recorded"].current() is True


def test_every_resamples_on_the_clock_and_holds():
    x = Every(Seq(range(1, 13)), 0.5)  # 30 s spans from the hour: the mean of each 3 cycles
    assert feed(x, 12) == [None, None, None, 2, 2, 2, 5, 5, 5, 8, 8, 8]  # out when the next span starts
    assert x.period == timedelta(seconds=30)
    assert feed(Every(Seq([1, None, 5, None, None, None, 0]), 0.5, "max"), 7) == [None, None, None, 5, 5, 5, None]


def test_windows_over_a_slow_input_keep_one_entry_per_value():
    hourly = Every(Seq([10] * 360 + [40] * 361), 60)  # two hours, one value each
    week = TsMean(hourly, 7 * 1440)
    feed(week, 721)
    assert [v for _, v in week.queue] == [10.0, 40.0] and week.current() == 25
    total = TsSum(Every(Seq([20] * 721), 60), 1440)  # 20 a minute, summed per hour
    assert feed(total, 721)[-1] == pytest.approx(20 * 120)


def test_delay_over_a_slow_input():
    assert feed(Delay(Every(Seq(range(1, 14)), 0.5), 0.5), 13)[-1] == 8  # 30 s back: the span before
    late = Delay(Every(Seq(range(1, 14)), 0.5), 1 / 3)  # 30 s spans, 20 s back
    fresh = []
    for i in range(13):
        Stream.tick(T0 + i * Stream.cycle, [late])
        fresh.append(late.fresh)
    assert fresh == [False] * 5 + [True, False, False] * 2 + [True, False]  # 20 s after each new span value


def test_ts_rank():
    assert feed(TsRank(Seq([3, 1, 2, 5, 4]), 5 / 6), 5) == [None, 0, 0.5, 1, 0.75]
    assert feed(TsRank(Seq([2, 2, 2]), 0.5), 3)[-1] == 0.5  # ties count half
    hours = Every(Seq([1] * 6 + [3] * 6 + [2] * 7), 1)  # three one-minute values
    assert feed(TsRank(hours, 60), 19)[-1] == 0.5  # 2 is between 1 and 3


def test_mixed_speeds():
    x = Seq(range(12))
    slow = Every(x, 0.5)
    both = Lift(lambda a, b: a - b, x, slow)
    assert feed(both, 6)[-1] == 5 - 1  # the live value minus the last closed span's mean (0, 1, 2)
    assert both.period is None  # each cycle


def test_expressions_use_slow_streams():
    primitives(kind_of)
    x = Signal("x", "ts_rank(every(keys, 1), 10)")
    run_to(10)
    assert x.current() == 0.5  # steady typing: every minute ties


class Saved:
    """A stand-in for the app's storage (core/store.py SignalHistory)."""

    def __init__(self, rows):
        self.rows = rows
        self.saved = []

    def load(self, name, since):
        return [row for row in self.rows.get(name, []) if row[0] > since]

    def save(self, name, t, value):
        self.saved.append((name, t, value))

    def forget(self, name, before):
        self.rows[name] = [row for row in self.rows.get(name, []) if row[0] > before]


def test_persisted_signals_reach_back_further_than_the_replay():
    old = [(at(-3 * 1440 + m), 50.0) for m in range(0, 60, 1)]  # 3 days ago, from an earlier run
    Stream.storage = Saved({"keys_1m": old})
    try:
        primitives(kind_of)
        Signal("keys_1m", "every(keys, 1)", backfill=True, window=timedelta(days=7), persist=True)
        week = Signal("week", "ts_mean(keys_1m, 7 * 1440)")
        replay(at(10), Record.of(at(-1440), at(10), RECORDED))
        assert week.current() == pytest.approx((60 * 50 + 10 * 20) / 70)  # the old hour and the last 10 minutes
        assert Stream.storage.saved[-1][:2] == ("keys_1m", at(10))  # type: ignore[union-attr]
    finally:
        Stream.storage = None


def test_a_saved_table_is_taken_as_it_is_up_to_its_last_row():
    Stream.storage = Saved({"doubled": [(at(5), 999.0)]})  # saved by an earlier run
    try:
        primitives(kind_of)
        doubled = Signal("doubled", "keys * 2", backfill=True, window=timedelta(days=7), persist=True)
        replay(at(10), Record.of(at(-1440), at(10), RECORDED))
        rows = doubled.history(at(-1440))
        assert rows[0] == (at(5), 999.0)  # as saved, nothing worked out before it
        assert rows[1] == (at(5) + Stream.cycle, 40.0) and rows[-1][0] == at(10)  # the cycles after it
    finally:
        Stream.storage = None


def test_tables_keep_their_window_or_as_far_as_their_inputs_reach():
    primitives(kind_of)
    short = Signal("short", "keys + 1", backfill=True, window=timedelta(minutes=1))
    follows = Signal("follows", "keys + 1", backfill=True)  # no window: as far as `keys` reaches
    replay(at(10), Record.of(at(-1440), at(10), RECORDED))
    assert [t for t, _ in short.history(at(-1440))] == [at(10) - i * Stream.cycle for i in range(5, -1, -1)]
    keys = Stream.registry["keys"]
    assert follows.history(at(-1440))[0][0] == keys.history(at(-1440))[0][0] and follows.reach() == keys.reach()


def test_a_signal_added_while_running_is_filled_in_from_the_tables():
    primitives(kind_of)
    early = Signal("early", "ts_mean(keys, 5)", backfill=True)
    replay(at(10), Record.of(at(-1440), at(10), RECORDED))
    late = Signal("late", "ts_mean(keys, 5)", backfill=True)  # added now: nothing fetched for it
    replay(at(10.5), Record.of(at(-1440), at(10.5), {}))
    assert late.history(at(-1440)) == early.history(at(-1440))  # the same day, from `keys`' table
    assert late.current() == early.current()


def test_input_rates_take_every_event_in_the_frame():
    """Events every 5 s, cycles every 10 s: both events of a frame count, not just one."""
    from proki.core.primitives import Keys

    keys = Keys()
    typing = [Event(at(i / 12), at((i + 1) / 12), {"presses": 2 * 6 if i % 2 else 0}) for i in range(24)]
    Stream.now = at(0)
    replay(at(2), Record.of(at(0), at(2), {"os.hid.input": typing}))
    assert keys.current() == pytest.approx(36)  # 6 presses in one 5 s event of each 10 s: 36 a minute


def test_unknown_instead_of_a_failed_cycle():
    assert feed(Lift(lambda a, b: a // b, Seq([7, 7]), Seq([2, 0])), 2) == [3, None]  # nothing the expression can't hold
    assert feed(Lift(lambda a, b: a > b, Seq(["Code"]), Constant(3)), 1) == [None]  # text where a number goes
    Stream.registry["zero"] = Constant(0)
    assert [compile_expr(e).current() for e in ("7 // zero", "7 % zero", "7 / zero")] == [None, None, None]


def test_and_or_know_the_answer_when_one_side_settles_it():
    Stream.registry["unknown"] = Constant(None)
    assert compile_expr("1 > 0 or unknown").current() is True
    assert compile_expr("1 > 2 and unknown").current() is False
    assert compile_expr("1 > 0 and unknown").current() is None
    assert compile_expr("1 > 2 or unknown").current() is None


def test_expression_mistakes_show_when_compiling():
    Stream.registry["keys"] = Seq([])
    for expr in ("ts_mean(keys)", "ts_mean(keys, keys)", "ts_mean(keys, True)", "every(keys, 'five')", "'a' + 1",
                 "ts_mean(keys, -5)"):
        with pytest.raises(ExprError):
            compile_expr(expr)
    compile_expr("delay(keys, 0)")  # x itself


def test_ts_sum_is_zero_once_its_window_empties():
    x = TsSum(Seq([0.1, 0.2, 0.7, 0.3] + [None] * 8), 1 / 6 * 4)  # 4 cycles
    assert feed(x, 12)[-1] == 0


def test_ts_count_skips_unknown_values_and_the_first_one():
    assert feed(TsCount(Seq(["Code", "Code", None, "Code", None, "Chrome"]), 5), 6)[-1] == 1


def test_every_takes_text_for_last_max_min():
    assert feed(Every(Seq(["Code", "Chrome", "Code", "Mail"]), 0.5, "last"), 4)[-1] == "Code"
    assert feed(Every(Seq(["b", "a", "c", "x"]), 0.5, "max"), 4)[-1] == "c"


def test_every_follows_the_local_clock():
    x = Every(Seq([1.0] * 3), 1440)
    midnight = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    for t in (midnight - 2 * Stream.cycle, midnight - Stream.cycle, midnight):
        Stream.tick(t, [x])
    assert x.fresh  # a day ends at local midnight (not UTC's)


def test_a_failed_fetch_moves_no_stream_on():
    primitives(kind_of)
    replay(at(10), Record.of(at(-1440), at(10), RECORDED))

    def down(bucket_type):
        raise ConnectionError("ActivityWatch stopped answering")

    with pytest.raises(OSError):
        replay(at(20), Record(at(10), at(20), down))
    assert Stream.now == at(10)  # the next run picks up from here: no cycle half done



def test_a_window_without_a_label_is_labeled_empty():
    primitives(lambda app, title: None)  # nothing is labeled
    run_to(10)
    assert Stream.registry["label"].current() == ""  # a window, no label: known
    assert compile_expr('label in ("email", "chat")').current() is False
    Stream.registry["unknown"] = Constant(None)
    assert compile_expr('unknown in ("email", "chat")').current() is None  # no window: unknown
