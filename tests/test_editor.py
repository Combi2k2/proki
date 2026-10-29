import json
from datetime import datetime, timedelta, timezone

import pytest

from conftest import built, programs_folder, replay_cycle, settle
import sqlite3

from proki import settings, storage
from proki.core.programs import Program
from proki.core.signals import Stream
from proki.engine import Engine
from proki.model import Defaults
from proki.programs.shipped import Shipped
from proki.tools.server import Tools
from proki.errors import ConfigError
from proki.programs.code.base import Ritual
from proki.services.activitywatch import Record

T0 = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)

CONFIG = {
    "inputs": [{"name": "time"}, {"name": "daytime"}],
    "variables": [{"name": "count", "value": 0}],
    "signals": [{"name": "hours", "expr": "daytime / 60"}],
    "rules": [{"name": "late", "lhs": "daytime", "cmp": "gt", "rhs": 1320}],
}
COUNTER = {"program": {"initial": "on", "states": {
    "on": {"do": [{"add": {"name": "count", "expr": "1"}}], "every": 0.1, "next": "on"}}}}


@pytest.fixture
def setup(tmp_path):
    return Engine(programs_folder(tmp_path, CONFIG, {"counter": COUNTER}), programs=[lambda: Ritual("@plan")])


async def cycle(e, minutes):
    t = T0 + timedelta(minutes=minutes)
    await replay_cycle(e, t, rec=Record.of(t - timedelta(minutes=1), t, {}))


def ask(e, **request):
    """What the editor's tools answer (tools/), with what proki ships as the defaults
    (kept in a database in memory): the result, or {"error": ...}."""
    if not hasattr(e, "tools"):
        db = sqlite3.connect(":memory:")
        db.executescript(storage.SCHEMA)
        e.tools = Tools(e, Shipped(settings.SHIPPED_DIR, storage.StateDB(db)))
    op = request.pop("op")
    tool = {"specs": "program_specs", "reference": "reference", "detail": "get_program", "switch": "switch_program",
            "revert": "reset_program"}.get(op, op)
    result = e.tools.call(tool, request)
    if result.is_error:
        return {"error": result.content[0].text}
    answer = json.loads(result.content[0].text)
    return {} if answer == {"ok": True} else answer


def test_the_specs_of_a_program_and_of_the_global_scope(setup):
    counter = ask(setup, op="specs", name="counter")
    assert counter["program"]["name"] == "counter" and [s["name"] for s in counter["states"]] == ["on"]
    [action] = counter["actions"]
    assert action == {"id": "counter.on.add", "program": "counter", "state": "on", "name": "add", "desc": "", "kind": "add",
                      "params": {"name": "count", "expr": "1"}}  # named after its kind, its id from where it is
    assert counter["branches"][0]["goto"] == "on" and not counter["default"]
    main = ask(setup, op="specs", name=None)
    assert [v["name"] for v in main["variables"]] == ["count"] and [i["name"] for i in main["inputs"]] == ["time", "daytime"]
    assert main["default"] and main["changed"]  # proki ships another one
    assert ask(setup, op="specs", name="nothing") == {"error": "no 'nothing'"}


async def test_a_mistake_is_said_and_nothing_changes(setup):
    await cycle(setup, 0)
    running, specs = Program.registry["counter"], setup.model.specs
    said = ask(setup, op="update_branch", program="counter", state="on", at=0, changes={"goto": "nowhere"})
    assert "nowhere" in said["error"]
    assert setup.model.specs is specs
    assert Program.registry["counter"] is running and "hours" in Stream.registry and "@plan" in Program.registry


async def test_a_change_runs_at_once(setup):
    await cycle(setup, 0)
    assert ask(setup, op="update_action", program="counter", state="on", at=0, changes={"params": {"name": "count", "expr": "2"}})
    before = Stream.registry["count"].value  # variables keep their values
    await cycle(setup, 1)
    assert Stream.registry["count"].value == before + 2
    assert set(Program.registry) == {"@plan", "counter"}  # the ones in code are made again too


async def test_a_new_program_with_what_it_brings(setup):
    said = ask(setup, op="apply_changes", changes=[
        {"op": "add", "kind": "program", "data": {"name": "ticker", "initial": "on"}},
        {"op": "add", "kind": "variable", "data": {"name": "ticks", "value": 0, "program": "ticker"}},
        {"op": "add", "kind": "action", "data": {"program": "ticker", "state": "on", "kind": "add", "params": {"name": "ticks", "expr": "count"}}}])
    assert "error" not in said and "ticker" in Program.registry
    assert [v["name"] for v in ask(setup, op="specs", name="ticker")["variables"]] == ["ticks"]  # it brings it


async def test_a_global_variables_value_is_changed_as_todays_lines_change_it(setup):
    said = ask(setup, op="apply_changes", changes=[{"op": "update", "kind": "variable", "data": {
        "name": "count", "scope": "global", "program": None, "state": None, "changes": {"value": 5}}}])
    assert "error" not in said and Stream.registry["count"].current() == 5
    lines = {"name": "lines", "scope": "global", "program": None, "state": None}
    said = ask(setup, op="apply_changes", changes=[{"op": "add", "kind": "variable", "data": {**lines, "value": "[0.35, 0.5]", "desc": ""}},
                                                   {"op": "update", "kind": "variable", "data": {**lines, "changes": {"value": "[0.2, 0.4, 0.6]"}}}])
    assert "error" not in said and ask(setup, op="set_value", name="lines", value=[0.2, 0.4, 0.6]) == {}  # as it starts, and now
    assert Stream.registry["lines"].current() == [0.2, 0.4, 0.6]
    assert [v.value for v in setup.model.specs.variables if v.name == "lines"] == ["[0.2, 0.4, 0.6]"]


async def test_the_reference_says_what_a_program_can_use(setup):
    await cycle(setup, 0)
    ref = ask(setup, op="reference")
    inputs = {i["name"]: i for i in ref["inputs"]}
    assert inputs["daytime"]["used"] and not inputs["keys_pressed"]["used"] and inputs["keys_pressed"]["desc"]
    assert {f["name"] for f in ref["functions"]} >= {"ts_mean", "every", "delay"}
    actions = {a["name"]: a for a in ref["actions"]}
    assert actions["ask_usr"]["params"][:2] == ["context", "result"] and "options?" in actions["ask_usr"]["params"]
    assert actions["ask_jev"]["params"] == ["context", "questions", "timeout?"] and actions["ask_llm"]["params"] == ["context", "result", "timeout?"]
    assert ref["signals"] == [{"name": "hours", "desc": "", "expr": "daytime / 60", "type": "number", "value": pytest.approx(ref["signals"][0]["value"]),
                               "backfill": None, "persist": False, "scope": "global", "app": False}]
    assert {"name": "count", "desc": "", "type": "number", "value": 1, "persist": True, "scope": "global", "from": "config", "app": False} in ref["variables"]
    assert ref["rules"][0]["name"] == "late"
    programs = {p["name"]: p for p in ref["programs"]}
    assert programs["counter"]["kind"] == "config" and programs["counter"]["state"] == "on"
    assert programs["@plan"]["kind"] == "code" and programs["@plan"]["desc"]



async def test_what_the_app_reads_is_kept(tmp_path):
    e = Engine(programs_folder(tmp_path, CONFIG, {}), reads={"count": "number", "hours": "number"})
    await cycle(e, 0)
    ref = ask(e, op="reference")
    assert [v["app"] for v in ref["variables"] if v["name"] == "count"] == [True] and ref["signals"][0]["app"]
    count = {"name": "count", "scope": "global", "program": None, "state": None}
    assert "the app reads count" in ask(e, op="apply_changes", changes=[{"op": "remove", "kind": "variable", "data": count}])["error"]
    assert "the app reads count" in ask(e, op="apply_changes", changes=[{"op": "update", "kind": "variable", "data": {**count, "changes": {"type": "string", "value": "'a'"}}}])["error"]
    assert "count" in Stream.registry


def test_a_check_compiles_aside(setup):
    registry, programs = dict(Stream.registry), dict(Program.registry)
    with pytest.raises(ConfigError):
        setup.check(Defaults.parse({"signals": [{"name": "x", "expr": "nothing_here"}]}, {}))
    assert Stream.registry == registry and Program.registry == programs  # the records the check made are let go: a task's held on the one that runs


async def test_a_program_goes_back_to_its_default():
    e = Engine(settings.SHIPPED_DIR)
    changed = lambda: ask(e, op="specs", name="day")["changed"]
    assert not changed()
    assert "error" not in ask(e, op="update_state", program="day", name="idle", changes={"every": 2})
    assert changed()
    assert ask(e, op="revert", name="day") == {} and not changed()
    assert "error" not in ask(e, op="add_program", name="mine")
    assert "no default" in ask(e, op="revert", name="mine")["error"]


async def test_a_programs_detail_goes_state_by_state(tmp_path):
    e = Engine(settings.SHIPPED_DIR)
    await cycle(e, 0)
    detail = ask(e, op="detail", name="pomodoro")
    assert detail["kind"] == "config" and detail["state"] == "idle"
    states = [s["name"] for s in detail["states"]]
    assert states[:3] == ["idle", "stopping", "starting"]  # as they're met from the initial one
    focusing = next(s for s in detail["states"] if s["name"] == "focusing")
    slipping = next(b for b in focusing["next"] if b["goto"] == "slipping")
    assert [r["name"] for r in slipping["rules"]] == ["session_low_focus", "session_not_recovering"]
    assert slipping["rules"][0]["lhs"] == "focus_2m" and slipping["conds"] == []
    done_yet = next(b for b in focusing["next"] if b["goto"] == "done_yet")
    assert {"expr": "not asked_done", "value": True} in done_yet["conds"]  # the program's own, as written
    starting = next(s for s in detail["states"] if s["name"] == "starting")
    assert starting["do"][0] == {"set": {"name": "session.requested", "expr": False}}
    assert ask(e, op="detail", name="nothing") == {"error": "no 'nothing'"}


async def test_a_program_shows_what_it_depends_on(tmp_path):
    e = Engine(settings.SHIPPED_DIR, programs=[lambda: TaggedRitual()])
    await cycle(e, 0)
    uses = ask(e, op="detail", name="pomodoro")["uses"]
    assert [r["name"] for r in uses["rules"]] == ["session_low_focus", "session_not_recovering"]
    signals = {s["name"] for s in uses["signals"]}
    assert {"session.minutes", "focus_2m", "focus", "active"} <= signals  # read, and what those read
    assert "deep_24h" not in signals and "session.daily" not in signals  # nobody here reads them
    variables = {v["name"]: v for v in uses["variables"]}
    assert variables["session.active"]["sets"] and variables["asked_done"]["sets"]  # its own, by its own name
    assert variables["done_yet.answer"]["sets"]  # a state's: its ask answers into it
    assert {"keys_pressed", "depth", "app_name", "time"} <= {i["name"] for i in uses["inputs"]}  # focus comes down to these
    assert ask(e, op="detail", name="@tagged")["uses"] == {"rules": [], "signals": [], "variables": [], "inputs": []}


class Kept:
    """Where the engine keeps the programs switched off, in memory."""

    def __init__(self, off=()):
        self.off = set(off)

    def load(self):
        return set(self.off)

    def save(self, off):
        self.off = set(off)


async def test_a_program_switched_off_stops_and_stays_off(tmp_path, ui):
    kept = Kept()
    e = Engine(settings.SHIPPED_DIR, switches=kept)
    await cycle(e, 0)
    bedtime = Program.registry["bedtime"]
    assert bedtime.on and bedtime.task is not None
    ask(e, op="switch", name="bedtime", on=False)
    await settle()
    assert not bedtime.on and bedtime.task is None and kept.off == {"bedtime"}
    await cycle(e, 1)
    assert bedtime.task is None  # the cycles leave it alone
    ref = {p["name"]: p for p in ask(e, op="reference")["programs"]}
    assert ref["bedtime"]["on"] is False and ref["suggest"]["on"] is True

    e.reload()  # and so does a reload, or a restart
    assert not Program.registry["bedtime"].on
    ask(e, op="switch", name="bedtime", on=True)
    await cycle(e, 2)
    assert Program.registry["bedtime"].task is not None and kept.off == set()


async def test_programs_say_what_theyre_for(tmp_path):
    e = Engine(settings.SHIPPED_DIR, programs=[lambda: TaggedRitual()])
    ref = {p["name"]: p for p in ask(e, op="reference")["programs"]}
    assert ref["bedtime"]["tags"] == ["sleep", "evening"] and ref["bedtime"]["desc"].startswith("Reminds you")
    assert (ref["bedtime"]["title"], ref["bedtime"]["icon"]) == ("Bedtime", "bed-double") and ref["@tagged"]["icon"] == ""
    assert Program.registry["@tagged"].tags == ["x"] and Program.registry["bedtime"].desc == ref["bedtime"]["desc"]
    assert ref["@tagged"]["tags"] == ["x"]


def test_desc_and_tags_are_checked(tmp_path):
    for spec, problem in [({"desc": 3}, "desc is a text"), ({"tags": "focus"}, "tags is a list"), ({"tags": [""]}, "a tag is a word"),
                          ({"icon": "Moon Star"}, "an icon is a name in-kebab-case"), ({"title": 1}, "title is a text")]:
        with pytest.raises(ValueError, match=problem):
            Engine(programs_folder(tmp_path, {}, {"p": spec}))


DESCRIBED = {
    "variables": [{"name": "n", "value": 0, "desc": "how many"}],
    "signals": [{"name": "half", "expr": "daytime / 2", "desc": "half the clock"}],
    "rules": [{"name": "early", "lhs": "daytime", "cmp": "lt", "rhs": 600, "desc": "before 10:00"}],
    "program": {"initial": "a", "variables": [{"name": "seen", "value": False, "desc": "seen yet"}], "states": {
        "a": {"desc": "waiting", "next": [{"goto": "b", "when": "early", "desc": "it's early"}, {"goto": "a"}]},
        "b": {"rules": [{"name": "late", "lhs": "daytime", "cmp": "gt", "rhs": 1200, "desc": "after 20:00"}],
              "next": [{"goto": "a", "when": "late"}]}}},
}


async def test_everything_says_what_its_for(tmp_path):
    e = Engine(programs_folder(tmp_path, {"inputs": [{"name": "daytime"}, {"name": "time"}]}, {"p": DESCRIBED}))
    await cycle(e, 0)
    ref = ask(e, op="reference")
    assert next(i for i in ref["inputs"] if i["name"] == "daytime")["desc"] == "the time of day, in minutes since midnight (0 to 1440)"
    assert next(s for s in ref["signals"] if s["name"] == "half")["desc"] == "half the clock"
    assert next(r for r in ref["rules"] if r["name"] == "early")["desc"] == "before 10:00"
    assert next(v for v in ref["variables"] if v["name"] == "n")["desc"] == "how many"
    rules = {r["name"]: r for r in ref["rules"]}
    assert rules["early"]["scope"] == "global" and rules["p.b.late"]["scope"] == "state"
    detail = ask(e, op="detail", name="p")
    a, b = detail["states"]
    assert a["desc"] == "waiting" and [w["desc"] for w in a["next"]] == ["it's early", ""]
    assert a["next"][0]["rules"][0]["desc"] == "before 10:00"
    assert b["desc"] == "" and b["next"][0]["rules"][0]["desc"] == "after 20:00"
    assert detail["vars"] == [{"name": "seen", "desc": "seen yet", "type": "boolean", "value": False, "persist": False}]


@pytest.mark.parametrize("where", ["signals", "rules", "variables", "state", "branch"])
def test_a_desc_is_a_line_of_text(tmp_path, where):
    
    spec = json.loads(json.dumps(DESCRIBED))
    entry = {"signals": spec["signals"][0], "rules": spec["rules"][0], "variables": spec["variables"][0],
             "state": spec["program"]["states"]["a"], "branch": spec["program"]["states"]["a"]["next"][0]}[where]
    entry["desc"] = ["not", "a", "line"]
    with pytest.raises(ConfigError, match="desc is a text"):
        built(programs_folder(tmp_path, {"inputs": [{"name": "daytime"}]}, {"p": spec}))


class TaggedRitual(Ritual):
    TAGS = ("x",)

    def __init__(self):
        super().__init__("@tagged")


def test_a_table_is_global_with_its_fields_and_an_object_of_variables_is_special(setup):
    rows = {v["name"]: v for v in ask(setup, op="reference")["variables"]}
    work, track = {f["name"]: f for f in rows["work"]["fields"]}, rows["track"]
    assert rows["work"]["scope"] == "special" and "work.tasks" not in rows  # its fields: under it
    assert {"work.tasks.id", "work.tasks.name", "work.tasks.ready"} <= {f["name"] for f in work["work.tasks"]["fields"]}
    assert "work.task.score" in {f["name"] for f in work["work.task"]["fields"]}  # one record
    assert track["scope"] == "special" and "track.now" in {f["name"] for f in track["fields"]} and "track.now" not in rows  # its fields: under it
    assert "work.plan" in work and "work.plan" not in rows  # a field of work's, an object


async def test_what_no_way_out_depends_on_is_taken_out_and_the_rest_stays(tmp_path):
    waiter = {"variables": [{"name": "left", "value": 0}], "program": {"initial": "on", "states": {
        "on": {"do": [{"set": {"name": "left", "expr": "hours"}}],  # set from one depended on: kept, and what it reads
               "next": [{"goto": "on", "when": ["left > 1", "late"]}, {"goto": "on"}]}}}}
    e = Engine(programs_folder(tmp_path, CONFIG, {"counter": COUNTER, "waiter": waiter}))
    said = ask(e, op="unused")["changes"]
    assert said == [{"op": "remove", "kind": "action", "data": {"program": "counter", "state": "on", "at": 0}},  # sets only count
                    {"op": "remove", "kind": "variable", "data": {"name": "count", "scope": "global", "program": None, "state": None}}]
    assert "error" not in ask(e, op="remove_unused")
    assert ask(e, op="unused")["changes"] == [] and "count" not in Stream.registry and "hours" in Stream.registry
