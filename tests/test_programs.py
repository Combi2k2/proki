import json
from datetime import datetime, timedelta, timezone

import pytest

from proki.compiler import compile_config
from proki.core.programs import Program
from conftest import replay, settle
from proki.core.later import Later
from proki.core.signals import Stream, Variable

T0 = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)


class Memory:
    def __init__(self):
        self.saved = {}

    def load(self, name):
        return self.saved[name]

    def save(self, name, value):
        self.saved[name] = value


class Value(Stream):
    """A stand-in input the test sets."""

    def __init__(self, name, value=None):
        self.name, self.value = name, value
        Stream.registry[name] = self

    def compute(self):
        return self.value


FOCUS = {
    "rules": [
        {"name": "high", "lhs": "x", "cmp": "gt", "rhs": 0.5},
        {"name": "low", "lhs": "x", "cmp": "lt", "rhs": 0.3},
        {"name": "many_pokes", "lhs": "pokes", "cmp": "ge", "rhs": 2},
    ],
    "programs": [
        {"name": "focus", "initial": "idle", "states": {
            "idle": {"next": [{"if": ["high"], "goto": "session.focusing"}]},
            "session.focusing": {"variables": [{"name": "pokes", "value": 0}], "every": 0.5,
                                 "next": [{"if": ["low"], "goto": "session.slipping"}]},
            "session.slipping": {"do": [{"add": {"name": "pokes", "expr": 1}}],
                                 "next": [{"if": ["many_pokes"], "goto": "idle"},
                                          {"if": ["high"], "goto": "session.focusing"}]},
        }},
    ],
}


def compiled(tmp_path, config):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    return compile_config(path)


def step(minutes, x=None, program="focus"):
    if x is not None:
        Stream.registry["x"].value = x
    Stream.now = T0 + timedelta(minutes=minutes)
    Stream.tick(Stream.now)
    Later.deliver()
    Program.tick(Stream.now)
    return Program.registry[program].current


def test_a_program_moves_through_its_states(tmp_path):
    Value("x", 0.0)
    compiled(tmp_path, FOCUS)
    assert step(0, 0.9) == "idle"  # its first turn: it enters its initial state
    assert step(1, 0.9) == "session.focusing"  # a minute later (every): high
    assert step(2, 0.1) == "session.slipping"
    assert Stream.registry["pokes"].current() == 1  # slipping's do, on entering
    assert step(3, 0.9) == "session.focusing"
    assert step(4, 0.1) == "session.slipping"
    assert step(5, 0.9) == "idle"  # many_pokes comes before high: the first branch that passes


def test_the_exit_is_tried_every_so_often(tmp_path):
    Value("x", 0.0)
    compiled(tmp_path, FOCUS)
    step(0, 0.9), step(1, 0.9)
    assert step(1.2, 0.1) == "session.focusing"  # entered 0.2 min ago: every 0.5
    assert step(1.5, 0.1) == "session.slipping"
    assert step(2, 0.5) == "session.slipping"  # entered at 1.5: not tried yet
    assert step(2.5, 0.5) == "session.slipping"  # tried: nothing passes, it stays
    assert step(3, 0.9) == "session.slipping"  # next try at 3.5
    assert step(3.5, 0.9) == "session.focusing"


def test_going_to_the_same_state_enters_it_again(tmp_path):
    config = {"variables": [{"name": "ticks", "value": 0}],
              "programs": [{"name": "count", "initial": "idle", "states": {
                  "idle": {"do": [{"add": {"name": "ticks", "expr": 1}}], "next": "idle"}}}]}
    compiled(tmp_path, config)
    for minute in range(4):
        step(minute, program="count")
    assert Stream.registry["ticks"].current() == 4  # its do, every time it's entered: once a minute


def test_a_state_without_an_exit_goes_back_to_idle(tmp_path):
    Value("x", 0.9)
    config = {"rules": FOCUS["rules"][:1], "programs": [{"name": "p", "initial": "idle", "states": {
        "idle": {"next": [{"if": ["high"], "goto": "done"}]},
        "done": {"every": 2}}}]}
    compiled(tmp_path, config)
    assert [step(m, program="p") for m in (0, 1, 2, 3)] == ["idle", "done", "done", "idle"]


ASK = {"variables": [{"name": "said", "value": 0}, {"name": "answer", "value": -2}],
       "programs": [{"name": "q", "initial": "idle", "states": {
           "idle": {"next": "asking"},
           "asking": {"do": [{"ask": {"channel": "usr", "context": "Start {n}?", "values": {"n": "1 + 1"},
                                      "options": [{"option": "Yes"}, {"option": "No"}],
                                      "result": "answer", "default": 1, "timeout": 30}}],
                      "every": 0.1,
                      "next": [{"goto": "yes", "if": "answer == 0"}, {"goto": "no", "if": "answer == 1"}]},
           "yes": {"do": [{"set": {"name": "said", "expr": 1}}], "next": [{"goto": "yes"}]},
           "no": {"do": [{"set": {"name": "said", "expr": -1}}], "next": [{"goto": "no"}]}}}]}


def test_an_answer_picks_the_next_state(tmp_path, ui):
    compiled(tmp_path, ASK)
    step(0, program="q"), step(1, program="q")
    assert Program.registry["q"].current == "asking"
    [request] = ui.questions(1)
    assert (request["context"], ui.labels(request)) == ("Start 2?", ["Yes", "No"])  # values filled in
    assert Stream.registry["answer"].current() is None  # waiting: unknown, so no branch passes
    assert step(1.1, program="q") == "asking"
    ui.click("Yes")
    assert step(1.2, program="q") == "yes" and Stream.registry["said"].current() == 1
    assert Stream.registry["answer"].current() == 0  # the chosen index


def test_no_answer_in_time_is_the_default(tmp_path, ui):
    config = json.loads(json.dumps(ASK))
    config["programs"][0]["states"]["asking"]["do"][0]["ask"]["timeout"] = 0.05  # seconds
    compiled(tmp_path, config)
    step(0, program="q"), step(1, program="q")
    [request] = ui.questions(1)
    settle()
    assert step(1.1, program="q") == "no"  # past its timeout: the default
    assert ui.sent == [{"type": "cancel", "id": request["id"]}]  # taken off the screen


def test_nobody_to_ask_is_the_default(tmp_path):
    compiled(tmp_path, ASK)  # nothing answers "proki.ask.usr"
    step(0, program="q"), step(1, program="q")
    settle()
    assert step(1.1, program="q") == "no"


def test_a_question_doesnt_hold_its_program(tmp_path, ui):
    Value("x", 0.0)
    config = {**ASK, "rules": [{"name": "high", "lhs": "x", "cmp": "gt", "rhs": 0.5}]}
    config["programs"] = json.loads(json.dumps(ASK["programs"]))
    config["programs"][0]["states"]["asking"]["next"].insert(0, {"goto": "no", "if": ["high"]})
    compiled(tmp_path, config)
    step(0, program="q"), step(1, program="q")
    assert step(1.1, 0.9, program="q") == "no"  # unanswered, and another branch passed


def test_states_are_not_streams(tmp_path):
    Value("x", 0.0)
    config = dict(FOCUS, signals=[{"name": "in_session", "expr": "focus.session"}])
    with pytest.raises(ValueError, match="not allowed in an expression"):
        compiled(tmp_path, config)


def test_a_restart_begins_at_the_initial_state_with_the_variables_kept(tmp_path):
    Variable.store = Memory()
    Value("x", 0.0)
    compiled(tmp_path, FOCUS)
    step(0, 0.9), step(1, 0.9), step(2, 0.1)
    assert Program.registry["focus"].current == "session.slipping"
    assert Variable.store.saved == {"pokes": 1}  # only variables are kept

    Stream.registry.clear(), Program.registry.clear()  # a restart
    Value("x", 0.0)
    compiled(tmp_path, FOCUS)
    assert Program.registry["focus"].current == "idle"  # back at its initial state
    assert Stream.registry["pokes"].current() == 1  # the variable carries over


def test_programs_are_checked(tmp_path):
    base = FOCUS["rules"][:2]  # high, low: they read x only
    ask = {"ask": {"channel": "usr", "context": "?", "options": [{"option": "A"}], "result": "v", "default": 0}}
    for states, problem in [
        ({"a": {"colour": 1}}, "unknown colour"),
        ({"a": {"next": [{"if": ["nope"], "goto": "a"}]}}, "no rule nope"),
        ({"a": {"next": "b"}}, "p has no state 'b'"),
        ({"a": {"next": [{"goto": "a"}, {"if": ["high"], "goto": "a"}]}}, "comes after the else"),
        ({"a": {"next": [{"if": "high", "goto": "a"}]}}, "'high' is a rule, so it goes in a list"),
        ({"a": {"next": [{"when": ["high"], "goto": "a"}]}}, "a branch is"),
        ({"a": {"next": "a", "every": 0}}, "every is in minutes"),
        ({"a": {"next": [{"goto": "a", "if": "nope > 1"}]}}, "unknown name 'nope'"),
        ({"a": {"next": [{"goto": "a", "if": 3}]}}, "if is a list of rules, or an expression"),
        ({"a": {}}, "no next, and no 'idle' state"),
        ({"a": {"do": [{"run": "q"}], "next": "a"}}, "an action is one of add, alarm, ask, lock, open, poke, set, sub"),
        ({"a": {"do": [{"goto": {"state": "a"}}], "next": "a"}}, "an action is one of"),
        ({"a": {"ask": {}, "next": "a"}}, "unknown ask"),
        ({"a": {"do": [{"ask": {**ask["ask"], "channel": "ai"}}], "next": "a"}}, "channel is one of usr, jev, llm"),
        ({"a": {"do": [{"ask": {**ask["ask"], "default": 1}}], "next": "a"}}, "default is an option's index, -1 to 0"),
        ({"a": {"do": [{"ask": {**ask["ask"], "default": True}}], "next": "a"}}, "default is an option's index"),
        ({"a": {"do": [{"ask": {**ask["ask"], "result": "nope"}}], "next": "a"}}, "result is a variable"),
        ({"a": {"do": [{"ask": {k: v for k, v in ask["ask"].items() if k != "result"}}], "next": "a"}}, "missing result"),
        ({"a": {"do": [{"ask": {**ask["ask"], "options": [{"option": "A", "goto": "a"}]}}], "next": "a"}}, "an option is"),
        ({"a": {"do": [{"ask": {**ask["ask"], "options": [{"option": "A"}, {"option": "A"}]}}], "next": "a"}}, "listed twice"),
        ({"a": {"do": [{"ask": {**ask["ask"], "timeout": -1}}], "next": "a"}}, "timeout is in seconds"),
        ({"a": {"do": [{"ask": {**ask["ask"], "values": {"n": "nope"}}}], "next": "a"}}, "unknown name 'nope'"),
        ({"a": {"do": [{"ask": {**ask["ask"], "values": ["v"]}}], "next": "a"}}, "values are"),
        ({"a": {"do": [{"ask": {**ask["ask"], "context": ""}}], "next": "a"}}, "context is"),
        ({"a": {"next": "a", "variables": [{"name": "high", "value": 1}]}}, "'high' is defined twice"),
    ]:
        Stream.registry.clear(), Program.registry.clear()
        from proki.core.rules import Rule
        Rule.registry.clear()
        Value("x", 0.0)
        with pytest.raises(ValueError, match=problem):
            compiled(tmp_path, {"rules": base, "variables": [{"name": "v", "value": 0}],
                                "programs": [{"name": "p", "initial": "a", "states": states}]})
    Stream.registry.clear(), Program.registry.clear(), Rule.registry.clear()
    with pytest.raises(ValueError, match="initial 'nowhere'"):
        compiled(tmp_path, {"programs": [{"name": "p", "initial": "nowhere", "states": {"a": {"next": "a"}}}]})


def test_the_shipped_day_program_moves_its_deadline_at_midnight():
    from proki.core.primitives import Primitive
    from proki.services.activitywatch import Record

    compile_config()
    deadline = Stream.registry["deadline_eod"]
    midnight = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    before, after = midnight - timedelta(minutes=2), midnight + timedelta(minutes=2)
    Stream.now = before
    replay(before + timedelta(minutes=1), Record.of(before, after, {}))
    Program.tick(Stream.now)
    assert deadline.current() == pytest.approx(midnight.timestamp() / 60)  # the next midnight
    replay(after, Record.of(before, after, {}))
    Program.tick(Stream.now)
    assert deadline.current() == pytest.approx(midnight.timestamp() / 60 + 1440)  # passed: the one after
    Program.tick(Stream.now + timedelta(minutes=5))
    assert deadline.current() == pytest.approx(midnight.timestamp() / 60 + 1440)  # once


def test_a_variable_declared_again_is_the_same_one(tmp_path):
    config = {
        "variables": [{"name": "count", "value": 1}, {"name": "label"}],
        "programs": [{"name": "p", "initial": "a", "states": {
            "a": {"variables": [{"name": "count"}], "next": "b"},              # no value: keeps 1
            "b": {"variables": [{"name": "label", "value": 7}], "next": "a"},  # a value: its starting value
        }}],
    }
    program = compiled(tmp_path, config)
    assert [v.name for v in program.variables] == ["count", "label"]  # one each
    assert Stream.registry["count"].current() == 1 and Stream.registry["label"].current() == 7
    states = Program.registry["p"].states
    assert states["a"].variables[0] is Stream.registry["count"]  # the global one, not a copy


def test_a_dot_is_only_part_of_a_name(tmp_path):
    """`b.c` is a state of its own: no `b` needed."""
    Value("x", 0.9)
    config = {"rules": FOCUS["rules"][:1], "programs": [{"name": "p", "initial": "b", "states": {
        "b": {"next": [{"if": ["high"], "goto": "b.c"}]},
        "b.c": {"next": [{"goto": "b.c"}]},
    }}]}
    compiled(tmp_path, config)
    assert [step(m, program="p") for m in (0, 1, 5)] == ["b", "b.c", "b.c"]


def test_a_jump_stays_in_its_own_program(tmp_path):
    Value("x", 0.9)
    config = {"rules": FOCUS["rules"][:1], "programs": [
        {"name": "p", "initial": "a", "states": {"a": {"next": "a"}}},
        {"name": "q", "initial": "b", "states": {"b": {"next": [{"if": ["high"], "goto": "a"}]}}},
    ]}
    with pytest.raises(ValueError, match="q has no state 'a'"):  # a is p's
        compiled(tmp_path, config)


def test_a_poke_is_a_notice(tmp_path, ui):
    config = {"programs": [{"name": "p", "initial": "idle", "states": {
        "idle": {"do": [{"poke": {"text": "{n} left", "values": {"n": "2 * 3"}}}], "next": [{"goto": "done"}]},
        "done": {"next": [{"goto": "done"}]}}}]}
    compiled(tmp_path, config)
    step(0, program="p")
    assert ui.sent == [{"type": "poke", "text": "6 left"}] and ui.requests == []  # one way: nothing to answer
