from datetime import datetime, timedelta, timezone

import pytest

from conftest import built, replay
from proki.core.rules import Rule
from proki.core.actions import Action, Add, Append, Remove, Set
from proki.core.primitives import Daytime, Dd, Mm, Primitive, Time, Weekday, Yy
from proki.core.signals import Signal, Stream, Variable
from proki.services.activitywatch import Event, Record

T0 = datetime(2026, 10, 1, 10, tzinfo=timezone.utc)  # a Thursday


def at(minutes):
    return T0 + timedelta(minutes=minutes)


class Memory:
    """A VariableStore in a dict (the app's is a table in proki.db)."""

    def __init__(self):
        self.saved = {}

    def load(self, name, type=None):
        return self.saved[name]

    def save(self, name, value, type=None):
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


async def test_updates_take_an_expression_at_the_moment():
    Daytime(), Time()
    last = Variable("last_suggested")
    count = Variable("count", 0)
    since = Signal("since_suggested", "time - last_suggested")
    remember = Set(name="last_suggested", expr="time")
    bump = Add(name="count", expr="1 + 1")
    clear = Set(name="last_suggested", expr=None)

    Stream.tick(at(0))
    await remember.apply(), await bump.apply()
    for m in range(1, 31):
        Stream.tick(at(m / 6))  # 5 minutes, a cycle each 10 s
    assert last.current() == pytest.approx(T0.timestamp() / 60)
    assert since.current() == pytest.approx(5)
    assert count.current() == 2
    await clear.apply()
    assert last.current() is None


async def test_an_action_works_its_expression_out_on_the_spot():
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
    await take.apply()
    assert Stream.registry["mean_then"].current() == pytest.approx(2.5)  # 0..5


def test_updates_are_checked():
    Variable("v", 0)
    Signal("s", "1")
    for entry, problem in [({"mul": {"name": "v", "expr": "1"}}, "an action is one of"),
                           ({"set": {}}, "set takes {name, expr, when}: missing expr, name"),
                           ({"set": {"v": "1"}}, "unknown v"),  # the old {variable: expr}
                           ({"set": {"name": "s", "expr": "1"}}, "no variable is called 's'"),
                           ({"set": {"name": "v", "expr": "nope + 1"}}, "unknown name"),
                           ({"goto": {"state": "idle"}}, "an action is one of"),  # a jump is a state's, not an action
                           ({"alarm": {"name": "bedtime", "on": True}}, "an action is one of"),  # an option of a poke now
                           ({"poke": {"context": "Up", "alarm": True}}, "unknown alarm"),  # a sound now
                           ({"poke": {"context": "Up", "title": 3}}, "title is a text")]:
        with pytest.raises(ValueError, match=problem):
            Action.parse(entry)
    Action.parse({"set": {"name": "nothing", "expr": "1"}})  # a name that's nobody's: a new variable
    assert Stream.registry["nothing"].current() is None
    with pytest.raises(ValueError, match="no variable is called 'nothing_here.x'"):  # a field of nobody's: not a name alone
        Action.parse({"set": {"name": "nothing_here.x", "expr": "1"}})


async def test_a_place_in_a_variable_is_set_the_rest_as_it_is():
    routines = Variable("routines", [{"name": "walk", "bins": [0, 0, 0]}, {"name": "read", "bins": [1, 1, 1]}])
    Variable("i", 1)
    for action in [Add(name="routines[i].bins[2]", expr="1"), Set(name="routines[-1].name", expr="'reading'"),
                   Add(name="routines[0].bins[-1]", expr="2"), Set(name="routines[0].bins[0]", expr="5", when="i == 0"),
                   Add(name="routines[5].bins[0]", expr="1"), Add(name="routines[i].bins[1.5]", expr="1")]:  # not there: nothing
        await action.apply()
    assert routines.current() == [{"name": "walk", "bins": [0, 0, 2]}, {"name": "reading", "bins": [1, 1, 2]}]


def test_a_place_is_checked_as_its_type_says():
    Variable("routines", [{"name": "walk", "bins": [0, 0, 0]}])
    Variable("n", 3)
    for action, problem in [(Set(name="routines[0].bins[0]", expr="'many'"), "bins\\[0\\] is of type number"),
                            (Set(name="routines.name", expr="'walk'"), "a column"),
                            (Add(name="routines[0].name", expr="1"), "adds and subtracts numbers"),
                            (Set(name="routines['walk'].name", expr="'x'"), "an item's place is a number")]:
        with pytest.raises(ValueError, match=problem):
            action.typecheck()
    with pytest.raises(ValueError, match="no variable is called"):
        Set(name="nothing[0]", expr="1")
    with pytest.raises(ValueError, match="no variable is called"):
        Set(name="(n + 1).x", expr="1")


async def test_an_item_is_appended_as_a_value_or_an_object_and_removed_by_its_id():
    times = Variable("times", [5], type={"type": "array", "items": {"type": "number"}})
    notes = Variable("notes", [{"id": 1, "text": "a"}, {"id": 2, "text": "b"}])
    for action in [Append(name="times", expr="5"), Append(name="notes", expr={"id": "3", "text": "'c'"}),
                   Remove(name="notes", id="2"), Remove(name="notes", id="None")]:  # an unknown id: nothing
        action.typecheck()
        await action.apply()
    assert times.current() == [5, 5] and notes.current() == [{"id": 1, "text": "a"}, {"id": 3, "text": "c"}]
    for action, problem in [(Append(name="times", expr={"value": "3"}), "not objects with fields"),
                            (Append(name="times", expr="'late'"), "items are of type number"),
                            (Remove(name="times", id="5"), "not objects with an id")]:
        with pytest.raises(ValueError, match=problem):
            action.typecheck()


async def test_actions_in_a_row_see_each_other():
    """A swap, through a third variable: each set reads what the one before it set."""
    a, b, tmp = Variable("a", 1), Variable("b", 2), Variable("tmp")
    swap = [Set(name="tmp", expr="a"), Set(name="a", expr="b"), Set(name="b", expr="tmp")]
    Stream.tick(T0)
    for action in swap:
        await action.apply()
    assert (a.current(), b.current()) == (2, 1)


def test_a_persisted_variable_keeps_its_latest_value():
    Variable.store = Memory()
    done = Variable("shutdown_done", False, persist=True)
    done.set(True)
    done.set(True)  # the same again: nothing written
    Variable("in_session", False).set(True)  # not persisted: never written
    assert Variable.store.saved == {"shutdown_done": True}
    Stream.registry.clear()  # a restart
    assert Variable("shutdown_done", False, persist=True).current() is True
    assert Variable("in_session", False).current() is False  # starts over
    assert Variable("never_set", 7, persist=True).current() == 7  # nothing saved: its starting value


def test_a_reset_goes_back_to_the_starting_value():
    Time(), Daytime()
    count, deadline = Variable("count", 0), Variable("deadline", "time + 10")
    Stream.tick(at(0))
    count.set(5), deadline.set(0)
    Stream.tick(at(30))
    count.reset(), deadline.reset()
    assert count.current() == 0
    assert deadline.current() == pytest.approx(at(30).timestamp() / 60 + 10)  # worked out now


def test_a_saved_value_of_another_kind_is_dropped():
    Variable.store = Memory()
    Variable.store.saved.update({"metric": "text", "flag": 1, "anything": 3})
    assert Variable("metric", 0, persist=True).current() == 0  # the config now wants a number
    assert Variable("flag", True, persist=True).current() is True  # 1 isn't a bool
    assert Variable("anything", None, persist=True).current() == 3  # null says nothing about the kind


def test_a_starting_expression_is_worked_out_once():
    Variable.store = Memory()
    Time(), Daytime()
    deadline = Variable("deadline_eod", "time - daytime + 1440", persist=True)  # the next midnight
    Stream.tick(at(0))
    midnight = (at(0).astimezone().replace(hour=0, minute=0, second=0) + timedelta(days=1)).timestamp() / 60
    assert deadline.current() == pytest.approx(midnight)
    assert Variable.store.saved["deadline_eod"] == pytest.approx(midnight)  # kept, like any change
    assert "deadline_eod.value" not in Stream.registry  # done with it
    Stream.tick(at(30))
    assert deadline.current() == pytest.approx(midnight)  # once, not every cycle
    Stream.registry.clear()
    Time(), Daytime()
    again = Variable("deadline_eod", "time - daytime + 1440", persist=True)
    Stream.tick(at(60 * 30))  # a day later: the saved deadline, not a new one
    assert again.current() == pytest.approx(midnight)


def test_the_app_keeps_variables_in_a_table(tmp_path):
    from proki.storage import VariableDB, connect

    db = connect(tmp_path / "proki.db")
    Variable.store = VariableDB(db)
    Variable("streak", 0, persist=True).set(3)
    rows = db.execute("SELECT name, value, updated_at FROM variables").fetchall()
    assert [(n, v) for n, v, _ in rows] == [("streak", "3")] and rows[0][2]
    Stream.registry.clear()
    assert Variable("streak", 0, persist=True).current() == 3


def test_a_list_of_objects_is_kept_as_a_table_of_its_own(tmp_path):
    from proki.storage import VariableDB, connect

    db    = connect(tmp_path / "proki.db")
    item  = {"type": "object", "properties": {"name": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}}}
    shelf = {"type": "array", "items": item}
    trip  = {"type": "object", "properties": {"to": {"type": "string"}, "stops": shelf}}
    Variable.store = VariableDB(db)
    Variable("books", None, persist=True, type=shelf).set([{"name": "Dune", "tags": ["sf"]}, {"name": "Emma"}])
    Variable("trip", None, persist=True, type=trip).set({"to": "Rome", "stops": [{"name": "Pisa"}]})
    assert db.execute("SELECT position, extra FROM var_books").fetchall() == [(0, '{"name": "Dune", "tags": ["sf"]}'), (1, '{"name": "Emma"}')]
    assert db.execute("SELECT value FROM variables WHERE name = 'trip'").fetchone() == ('{"to": "Rome", "stops": []}',)  # its stops: a table
    Stream.registry.clear()
    assert Variable("books", None, persist=True, type=shelf).current() == [{"name": "Dune", "tags": ["sf"]}, {"name": "Emma"}]
    assert Variable("trip", None, persist=True, type=trip).current() == {"to": "Rome", "stops": [{"name": "Pisa"}]}
    Variable("grid", None, persist=True, type={"type": "array", "items": shelf}).set([[{"name": "Dune"}]])
    assert db.execute("SELECT value FROM variables WHERE name = 'grid'").fetchone() == ('[[{"name": "Dune"}]]',)  # no name, no table: as it is


def test_a_list_of_objects_inside_an_item_of_one_is_a_table_under_it(tmp_path):
    from proki.core.signals import Expr
    from proki.storage import VariableDB, connect, list_paths

    db    = connect(tmp_path / "proki.db")
    step  = {"type": "object", "properties": {"say": {"type": "string"}}}
    task  = {"type": "object", "properties": {"name": {"type": "string"}, "steps": {"type": "array", "items": step}}}
    group = {"type": "object", "properties": {"name": {"type": "string"}, "tasks": {"type": "array", "items": task}}}
    shape = {"type": "array", "items": group}
    assert list_paths(shape) == ["", "tasks", "tasks.steps"]
    value = [{"name": "School", "tasks": [{"name": "Essay", "steps": [{"say": "outline"}, {"say": "draft"}]}, {"name": "Read", "steps": []}]},
             {"name": "Home", "tasks": [{"name": "Dishes"}]}]
    Variable.store = VariableDB(db)
    Variable("groups", None, persist=True, type=shape).set(value)
    assert db.execute("SELECT value FROM variables WHERE name = 'groups'").fetchone() == ("[]",)
    assert db.execute("SELECT id, parent, position, extra FROM var_groups_tasks").fetchall() == [
        (1, 1, 0, '{"name": "Essay", "steps": []}'), (2, 1, 1, '{"name": "Read", "steps": []}'), (3, 2, 0, '{"name": "Dishes"}')]  # under its group
    assert db.execute("SELECT parent, extra FROM var_groups_tasks_steps").fetchall() == [(1, '{"say": "outline"}'), (1, '{"say": "draft"}')]
    Stream.registry.clear()
    assert Variable("groups", None, persist=True, type=shape).current() == value
    assert Expr("groups.tasks.name").value() == ["Essay", "Read", "Dishes"]  # every group's tasks, one list
    assert Expr("groups[0].tasks.steps.say").value() == ["outline", "draft"]
    assert Expr("groups.tasks").type == {"type": "array", "items": task}


def test_the_time_of_the_cycle():
    daytime, weekday, time, dd, mm, yy = Daytime(), Weekday(), Time(), Dd(), Mm(), Yy()
    Stream.tick(at(90.5))
    local = at(90.5).astimezone()
    assert daytime.current() == pytest.approx(local.hour * 60 + local.minute + 0.5)
    assert weekday.current() == local.weekday()
    assert time.current() == pytest.approx(at(90.5).timestamp() / 60)
    assert (dd.current(), mm.current(), yy.current()) == (local.day, local.month, local.year) == (1, 10, 2026)
    assert (dd.type, mm.type, yy.type) == ("integer", "integer", "integer")
    Stream.now = None
    assert daytime.compute() is None  # no cycle yet: unknown


def test_the_time_is_known_without_a_recording():
    """The clock's primitives don't need ActivityWatch: they're known while nothing was recorded."""
    Daytime()
    Stream.now = at(0)
    replay(at(1), Record.of(at(0), at(1), {}))
    assert Stream.registry["daytime"].current() is not None


def test_config_variables(tmp_path):
    Variable.store = Memory()
    Variable.store.saved["sessions_today"] = 4
    config = tmp_path / "main.json"
    config.write_text('''{
      "inputs": [{"name": "time"}, {"name": "keys_pressed", "backfill": 60}],
      "variables": [{"name": "last_suggested", "value": null},
                    {"name": "sessions_today", "value": 0},
                    {"name": "deadline_eod", "value": "time + since_suggested_default"}],
      "signals": [{"name": "since_suggested", "expr": "time - last_suggested"},
                  {"name": "since_suggested_default", "expr": "60"}],
      "rules": [{"name": "not_lately", "lhs": "since_suggested", "cmp": "gt", "rhs": 45}]
    }''')
    program = built(config.parent)
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
    bad = tmp_path / "main.json"
    for text, problem in [('{"variables": [{"name": "v", "value": [1, 2]}]}', "value is true or false or a number"),
                          ('{"variables": [{"name": "v", "value": 0, "persist": true}]}', "unknown persist"),  # a global one always is
                          ('{"variables": [{"name": "v", "value": "nope + 1"}]}', "'v': unknown name 'nope'"),
                          ('{"variables": [{"name": "v", "vale": 1}]}', "unknown vale"),
                          ('{"variables": [{"value": 1}]}', "name is missing"),
                          ('{"variables": [{"name": "v"}], "signals": [{"name": "v", "expr": "1"}]}', "twice")]:
        bad.write_text(text)
        Stream.registry.clear()
        with pytest.raises(ValueError, match=problem):
            built(bad.parent)


async def test_a_change_is_read_at_once_and_worked_out_from_the_next_cycle():
    """A variable reads as it's set at once; what's worked out from it, from the next cycle on."""
    x = Variable("x", 0)
    bump = Set(name="x", expr="x + 1")
    doubled = Signal("doubled", "x * 2")
    Stream.tick(T0)
    assert doubled.current() == 0
    await bump.apply(), await bump.apply()  # twice in one cycle: each reads it as it is
    assert x.current() == 2 and doubled.current() == 0
    Stream.tick(T0 + Stream.cycle)
    assert doubled.current() == 4


def test_a_starting_expression_waits_for_the_live_cycle():
    now = at(60 * 15)
    Time(), Daytime(), Primitive.kinds["keys_pressed"](backfill=True, window=timedelta(days=1))
    deadline = Variable("deadline_eod", "time - daytime + 1440")
    replay(now, Record.of(now - timedelta(days=1), now, {}))  # the startup replay: a day back
    midnight = (now.astimezone().replace(hour=0, minute=0, second=0) + timedelta(days=1)).timestamp() / 60
    assert deadline.current() == pytest.approx(midnight)  # tonight's, not the one a day ago

