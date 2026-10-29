"""The programs' model: specs changed by add, update and remove, each checked by building
it aside before it's kept (proki/model/)."""

from datetime import datetime, timedelta, timezone

import pytest

from conftest import programs_folder, replay_cycle
from proki.core.programs import Program
from proki.core.rules import Rule
from proki.core.signals import Stream
from proki.engine import Engine
from proki.errors import ConfigError
from proki.core.rules import COMPARE
from proki.model.specs import Compare, Spec
from proki.programs.code.base import Ritual
from proki.services.activitywatch import Record

T0 = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)

MAIN = {"inputs": [{"name": "time"}, {"name": "daytime"}],
        "signals": [{"name": "hours", "expr": "daytime / 60", "desc": "the clock, in hours"}]}


@pytest.fixture
def engine(tmp_path):
    return Engine(programs_folder(tmp_path, MAIN), programs=[lambda: Ritual("@plan")])


async def cycle(e, minutes):
    t = T0 + timedelta(minutes=minutes)
    await replay_cycle(e, t, rec=Record.of(t - timedelta(minutes=1), t, {}))


async def test_a_program_is_made_node_by_node_and_runs(engine):
    model = engine.model
    model.add("program", {"name": "late", "desc": "late at night: a poke"})
    assert Program.registry["late"].states.keys() == {"idle"}  # its initial state, made with it
    model.add("variable", {"name": "pokes", "value": 0, "scope": "program", "program": "late"})
    model.add("rule", {"name": "night", "lhs": "hours", "cmp": "ge", "rhs": 0, "scope": "program", "program": "late"})
    model.add("state", {"program": "late", "name": "poking", "every": 0.1})
    model.add("action", {"program": "late", "state": "poking", "kind": "add", "params": {"name": "pokes", "expr": 1}})
    model.add("branch", {"program": "late", "state": "idle", "goto": "poking", "when": ["night"], "desc": "it's late"})
    await cycle(engine, 0), await cycle(engine, 1)
    assert Stream.registry["late.pokes"].current() == 1  # its own variable, by its full name
    assert Program.registry["late"].states["idle"].next[0].desc == "it's late"


def test_a_mistake_is_said_and_nothing_changes(engine):
    model, before = engine.model, engine.model.specs
    for kind, data, problem in [
        ("signal", {"name": "x", "expr": "nothing_here + 1"}, "signal 'x': unknown name 'nothing_here'"),
        ("rule", {"name": "r", "lhs": 1, "cmp": "gx", "rhs": 2}, "cmp is one of gt"),  # the shape
        ("rule", {"name": "r", "lhs": "hours", "cmp": "gt"}, "rule .r.: rhs is missing"),
        ("signal", {"name": "hours", "expr": "1"}, "signal 'hours' is there already"),
        ("variable", {"name": "v", "scope": "state", "program": "p"}, "scope state takes its program and its state"),
        ("branch", {"program": "@plan", "state": "on", "goto": "on"}, "a name is letters"),  # a program in code
    ]:
        with pytest.raises(ConfigError, match=problem):
            model.add(kind, data)
        assert model.specs is before and "x" not in Stream.registry


def test_removing_takes_what_it_owns_and_stops_at_what_is_read(engine):
    model = engine.model
    model.apply([("add", "program", {"name": "p"}),
                 ("add", "rule", {"name": "early", "lhs": "hours", "cmp": "lt", "rhs": 9, "program": "p"}),  # global, brought by p
                 ("add", "variable", {"name": "seen", "scope": "program", "program": "p"}),
                 ("add", "state", {"program": "p", "name": "done"}),
                 ("add", "branch", {"program": "p", "state": "idle", "goto": "done", "when": ["early"]})])
    with pytest.raises(ConfigError, match="unknown name 'hours'"):
        model.remove("signal", {"name": "hours"})  # the rule p brings reads it
    with pytest.raises(ConfigError, match="no state 'done'"):
        model.remove("state", {"program": "p", "name": "done"})  # idle goes to it
    gone = model.remove("program", {"name": "p"})
    assert {(g.get("name"), g.get("goto")) for g in gone} >= {("p", None), ("early", None), ("seen", None), ("done", None), (None, "done")}
    assert "early" not in Rule.registry and "p" not in Program.registry
    model.remove("signal", {"name": "hours"})  # nothing reads it now


def test_changes_together_are_kept_together(engine):
    model = engine.model
    with pytest.raises(ConfigError, match="no state 'b'"):
        model.apply([("add", "program", {"name": "p"}),
                     ("add", "branch", {"program": "p", "state": "idle", "goto": "b"})])  # b never comes
    assert "p" not in Program.registry and model.all("program") == []
    model.apply([("add", "program", {"name": "p"}),
                 ("add", "branch", {"program": "p", "state": "idle", "goto": "b"}),  # b comes next: fine together
                 ("add", "state", {"program": "p", "name": "b"})])
    assert Program.registry["p"].states["idle"].next[0].goto == "b"


def test_ways_out_are_placed_and_found_by_their_place(engine):
    model = engine.model
    model.apply([("add", "program", {"name": "p"}), ("add", "state", {"program": "p", "name": "a"}),
                 ("add", "branch", {"program": "p", "state": "idle", "goto": "idle"})])
    model.add("branch", {"program": "p", "state": "idle", "goto": "a", "when": ["hours > 25"], "at": 0})  # before the else
    assert [b.goto for b in Program.registry["p"].states["idle"].next] == ["a", "idle"]
    model.update("branch", {"program": "p", "state": "idle", "at": 0}, {"desc": "never"})
    assert model.get("branch", {"program": "p", "state": "idle", "at": 0})["desc"] == "never"
    with pytest.raises(ConfigError, match="after the else"):
        model.add("branch", {"program": "p", "state": "idle", "goto": "a"})  # last, after the else


def test_a_renamed_program_takes_what_it_owns(engine):
    model = engine.model
    model.apply([("add", "program", {"name": "p"}),
                 ("add", "variable", {"name": "n", "value": 0, "scope": "state", "program": "p", "state": "idle"})])
    model.update("program", {"name": "p"}, {"name": "q"})
    assert "q.idle.n" in Stream.registry and "p" not in Program.registry
    assert model.get("variable", {"name": "n", "scope": "state", "program": "q", "state": "idle"})["value"] == 0


def test_every_kind_has_a_schema():
    for kind, cls in Spec.kinds.items():
        shape = cls.schema()
        assert shape["type"] == "object" and shape["description"] and set(shape["required"]) <= set(shape["properties"])
        assert all(p["description"] for p in shape["properties"].values()), kind
    assert Spec.kinds["branch"].schema()["properties"]["when"]["type"] == "array"
    assert Spec.kinds["rule"].schema()["properties"]["cmp"]["enum"] == ["gt", "ge", "lt", "le", "eq", "ne"]
    assert Spec.kinds["branch"].parse({"program": "p", "state": "a", "goto": "b", "when": ["x"]}).when == ["x"]
    assert set(Compare.__args__) == set(COMPARE)  # written out for the type checker, the same as core's


def test_main_json_swapped_leaves_the_programs(engine):
    """The global scope back to what a main.json says: the programs stay as they are."""
    from proki.model import Defaults

    model = engine.model
    model.add("program", {"name": "p"})
    model.swap(None, Defaults.parse({"inputs": [{"name": "time"}, {"name": "daytime"}],
                                    "signals": [{"name": "hours", "expr": "daytime / 60"}, {"name": "half", "expr": "daytime / 2"}]}, {}))
    assert "p" in Program.registry and {"hours", "half"} <= set(Stream.registry)


def test_an_action_gets_an_id_and_keeps_it(engine):
    model = engine.model
    model.add("program", {"name": "p"})
    id = model.add("action", {"program": "p", "state": "idle", "kind": "poke", "params": {"context": "Hi"}})["id"]
    other = model.add("action", {"program": "p", "state": "idle", "kind": "lock"})["id"]
    assert id and other and id != other
    changed = model.update("action", {"program": "p", "state": "idle", "at": 0}, {"params": {"context": "Hello"}})
    assert changed["id"] == id  # changed: its id stays
    model.apply([("remove", "action", {"program": "p", "state": "idle", "at": 0}),
                 ("add", "action", {**changed, "at": 1})])  # moved: the same
    assert [a["id"] for a in model.all("action", program="p")] == [other, id]
    with pytest.raises(ConfigError, match="is another action's"):
        model.add("action", {"program": "p", "state": "idle", "kind": "poke", "params": {"context": "Hi"}, "id": id})


def test_an_action_is_named_its_id_made_from_where_it_is_and_kept(engine):
    model = engine.model
    model.add("program", {"name": "p"})
    model.add("state", {"program": "p", "name": "asking"})
    first = model.add("action", {"program": "p", "state": "asking", "kind": "poke", "params": {"context": "Hi"}})
    second = model.add("action", {"program": "p", "state": "asking", "kind": "poke", "params": {"context": "Hey"}, "desc": "a second hello"})
    assert (first["name"], first["id"]) == ("poke", "p.asking.poke") and (second["name"], second["id"]) == ("poke_2", "p.asking.poke_2")
    with pytest.raises(ConfigError, match="is there already"):
        model.add("action", {"program": "p", "state": "asking", "name": "poke", "kind": "lock"})  # a name of its own in its state
    model.update("state", {"program": "p", "name": "asking"}, {"name": "greeting"})
    assert [a["id"] for a in model.all("action", program="p")] == ["p.asking.poke", "p.asking.poke_2"]  # renamed: the ids stay
