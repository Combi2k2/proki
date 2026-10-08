from datetime import datetime, timedelta, timezone

import pytest

from conftest import replay
from proki.compiler import compile_config
from proki.core.rules import Rule
from proki.core.actions import Action, Add, Set
from proki.core.primitives import Clock, Primitive, Time, Weekday
from proki.core.signals import Signal, Stream, Variable
from proki.services.activitywatch import Event, Record

T0 = datetime(2026, 10, 1, 10, tzinfo=timezone.utc)  # a Thursday


def at(minutes):
    return T0 + timedelta(minutes=minutes)


class Memory:
    """A VariableStore in a dict (the app's is a table in proki.db)."""

    def __init__(self):
        self.saved = {}

    def load(self, name):
        return self.saved[name]

    def save(self, name, value):
        self.saved[name] = value


def test_set_add_sub_and_unknown():
    pokes = Variable("pokes", 0)
    pokes.add(2)
    pokes.sub(0.5)
    assert pokes.current() == 1.5
    pokes.set(None)
    pokes.add(1)  # adding to an unknown value keeps it unknown
    assert pokes.current() is None
    pokes.set(3)
    pokes.add(None)  # an unknown amount changes nothing
    assert pokes.current() == 3


def test_a_change_shows_in_the_same_cycle():
    flag = Variable("flag", False)
    Stream.tick(T0)
    assert flag.current() is False
    flag.set(True)  # between cycles (an answer to a popup)
    assert flag.current() is True
    doubled = Signal("doubled", "flag * 2")
    Stream.tick(T0 + Stream.cycle)
    assert doubled.current() == 2  # expressions read it like any stream


def test_updates_take_an_expression_at_the_moment():
    Clock(), Time()
    last = Variable("last_suggested")
    count = Variable("count", 0)
    since = Signal("since_suggested", "time - last_suggested")
    remember = Set(name="last_suggested", expr="time")
    bump = Add(name="count", expr="1 + 1")
    clear = Set(name="last_suggested", expr=None)

    Stream.tick(at(0))
    remember.apply(), bump.apply()
    for m in range(1, 31):
        Stream.tick(at(m / 6))  # 5 minutes, a cycle each 10 s
    assert last.current() == pytest.approx(T0.timestamp() / 60)
    assert since.current() == pytest.approx(5)
    assert count.current() == 2
    clear.apply()
    assert last.current() is None


def test_an_action_works_its_expression_out_on_the_spot():
    """No window in an action (nothing moves it on every cycle for the action): a signal's
    name instead, which moves on with the others."""
    Variable("x", 0)
    Variable("mean_then")
    with pytest.raises(ValueError, match="ts_mean keeps a window"):
        Set(name="mean_then", expr="ts_mean(x, 1)")
    Signal("x_1m", "ts_mean(x, 1)")
    take = Set(name="mean_then", expr="x_1m * 1")  # names, and arithmetic over them: fine
    for i in range(6):
        Stream.registry["x"].set(i)
        Stream.tick(at(i / 6))
    take.apply()
    assert Stream.registry["mean_then"].current() == pytest.approx(2.5)  # 0..5


def test_updates_are_checked():
    Variable("v", 0)
    Signal("s", "1")
    for entry, problem in [({"mul": {"name": "v", "expr": "1"}}, "an action is one of"),
                           ({"set": {}}, "set takes {name, expr}: missing expr, name"),
                           ({"set": {"v": "1"}}, "unknown v"),  # the old {variable: expr}
                           ({"set": {"name": "nothing", "expr": "1"}}, "no variable"),
                           ({"set": {"name": "s", "expr": "1"}}, "no variable is called 's'"),
                           ({"set": {"name": "v", "expr": "nope + 1"}}, "unknown name"),
                           ({"goto": {"state": "idle"}}, "an action is one of"),  # a jump is a state's, not an action
                           ({"alarm": {"name": "bedtime", "on": "yes"}}, "on is true")]:
        with pytest.raises(ValueError, match=problem):
            Action.parse(entry)


def test_actions_in_a_row_see_each_other():
    """A swap, through a third variable: each set reads what the one before it set."""
    a, b, tmp = Variable("a", 1), Variable("b", 2), Variable("tmp")
    swap = [Set(name="tmp", expr="a"), Set(name="a", expr="b"), Set(name="b", expr="tmp")]
    Stream.tick(T0)
    for action in swap:
        action.apply()
    assert (a.current(), b.current()) == (2, 1)


def test_every_variable_keeps_its_latest_value():
    Variable.store = Memory()
    done = Variable("shutdown_done", False)
    done.set(True)
    done.set(True)  # the same again: nothing written
    assert Variable.store.saved == {"shutdown_done": True}
    Stream.registry.clear()  # a restart
    assert Variable("shutdown_done", False).current() is True
    assert Variable("never_set", 7).current() == 7  # nothing saved: its starting value


def test_a_saved_value_of_another_kind_is_dropped():
    Variable.store = Memory()
    Variable.store.saved.update({"metric": "text", "flag": 1, "anything": 3})
    assert Variable("metric", 0).current() == 0  # the config now wants a number
    assert Variable("flag", True).current() is True  # 1 isn't a bool
    assert Variable("anything", None).current() == 3  # null says nothing about the kind


def test_a_starting_expression_is_worked_out_once():
    Variable.store = Memory()
    Time(), Clock()
    deadline = Variable("deadline_eod", "time - clock + 1440")  # the next midnight
    Stream.tick(at(0))
    midnight = (at(0).astimezone().replace(hour=0, minute=0, second=0) + timedelta(days=1)).timestamp() / 60
    assert deadline.current() == pytest.approx(midnight)
    assert Variable.store.saved["deadline_eod"] == pytest.approx(midnight)  # kept, like any change
    assert "deadline_eod.value" not in Stream.registry  # done with it
    Stream.tick(at(30))
    assert deadline.current() == pytest.approx(midnight)  # once, not every cycle
    Stream.registry.clear()
    Time(), Clock()
    again = Variable("deadline_eod", "time - clock + 1440")
    Stream.tick(at(60 * 30))  # a day later: the saved deadline, not a new one
    assert again.current() == pytest.approx(midnight)


def test_the_app_keeps_variables_in_a_table(tmp_path):
    from proki.legacy.core.store import Store, VariableValues

    store = Store(tmp_path / "proki.db")
    Variable.store = VariableValues(store)
    Variable("streak", 0).set(3)
    rows = store._db.execute("SELECT name, value, updated_at FROM variables").fetchall()
    assert [(n, v) for n, v, _ in rows] == [("streak", "3")] and rows[0][2]
    Stream.registry.clear()
    assert Variable("streak", 0).current() == 3


def test_the_time_of_the_cycle():
    clock, weekday, time = Clock(), Weekday(), Time()
    Stream.tick(at(90.5))
    local = at(90.5).astimezone()
    assert clock.current() == pytest.approx(local.hour * 60 + local.minute + 0.5)
    assert weekday.current() == local.weekday()
    assert time.current() == pytest.approx(at(90.5).timestamp() / 60)
    Stream.now = None
    assert clock.compute() is None  # no cycle yet: unknown


def test_the_time_is_known_without_a_recording():
    """Clock primitives don't need ActivityWatch: they're known while nothing was recorded."""
    Clock()
    Stream.now = at(0)
    replay(at(1), Record.of(at(0), at(1), {}))
    assert Stream.registry["clock"].current() is not None


def test_config_variables(tmp_path):
    Variable.store = Memory()
    Variable.store.saved["sessions_today"] = 4
    config = tmp_path / "config.json"
    config.write_text('''{
      "inputs": [{"name": "time"}, {"name": "keys", "backfill": 60}],
      "variables": [{"name": "last_suggested", "value": null},
                    {"name": "sessions_today", "value": 0},
                    {"name": "deadline_eod", "value": "time + since_suggested_default"}],
      "signals": [{"name": "since_suggested", "expr": "time - last_suggested"},
                  {"name": "since_suggested_default", "expr": "60"}],
      "rules": [{"name": "not_lately", "lhs": "since_suggested", "cmp": "gt", "rhs": 45}]
    }''')
    program = compile_config(config)
    names = [v.name for v in program.variables]
    assert names == ["last_suggested", "sessions_today", "deadline_eod"]
    assert program.variables[1].current() == 4  # restored
    assert set(names) <= {s.name for s in program.streams}

    typing = [Event(at(m / 12), at((m + 1) / 12), {"presses": 5}) for m in range(60 * 12)]
    Stream.now = at(0)
    replay(at(10), Record.of(at(0), at(10), {"os.hid.input": typing}))
    assert Rule.registry["not_lately"].chance() == 0  # never suggested: unknown, so it never fires
    program.variables[0].set(Stream.registry["time"].current())
    replay(at(60), Record.of(at(0), at(60), {"os.hid.input": typing}))
    assert Stream.registry["since_suggested"].current() == pytest.approx(50)
    assert Rule.registry["not_lately"].chance() == 1


def test_config_variables_are_checked(tmp_path):
    bad = tmp_path / "config.json"
    for text, problem in [('{"variables": [{"name": "v", "value": [1, 2]}]}', "a value is a number"),
                          ('{"variables": [{"name": "v", "value": 0, "persist": true}]}', "unknown persist"),
                          ('{"variables": [{"name": "v", "value": "nope + 1"}]}', "'v': unknown name 'nope'"),
                          ('{"variables": [{"name": "v", "vale": 1}]}', "unknown vale"),
                          ('{"variables": [{"value": 1}]}', "needs a name"),
                          ('{"variables": [{"name": "v"}], "signals": [{"name": "v", "expr": "1"}]}', "twice")]:
        bad.write_text(text)
        Stream.registry.clear()
        with pytest.raises(ValueError, match=problem):
            compile_config(bad)


def test_a_change_is_seen_at_once_by_everything_that_reads_it():
    """Values worked out earlier in the cycle are worked out again after a variable changes."""
    x = Variable("x", 0)
    bump = Set(name="x", expr="x + 1")
    doubled = Signal("doubled", "x * 2")
    Stream.tick(T0)
    assert doubled.current() == 0
    bump.apply(), bump.apply()  # twice in one cycle
    assert x.current() == 2 and doubled.current() == 4


def test_a_starting_expression_waits_for_the_live_cycle():
    now = at(60 * 15)
    Time(), Clock(), Primitive.kinds["keys"](backfill=True, window=timedelta(days=1))
    deadline = Variable("deadline_eod", "time - clock + 1440")
    replay(now, Record.of(now - timedelta(days=1), now, {}))  # the startup replay: a day back
    midnight = (now.astimezone().replace(hour=0, minute=0, second=0) + timedelta(days=1)).timestamp() / 60
    assert deadline.current() == pytest.approx(midnight)  # tonight's, not the one a day ago
