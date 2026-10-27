import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from proki import settings
from proki.channels.popup import Popup
from proki.core.programs import Program
from proki.core.rules import Rule
from conftest import built, programs_folder, replay, settle, tick
from proki.core.signals import Stream, Variable

T0 = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)


class Memory:
    def __init__(self):
        self.saved = {}

    def load(self, name, type=None):
        return self.saved[name]

    def save(self, name, value, type=None):
        self.saved[name] = value


class Value(Stream):
    """A stand-in input the test sets."""

    def __init__(self, name, value=None):
        self.name, self.value = name, value
        Stream.registry[name] = self

    def compute(self):
        return self.value


FOCUS = {
    "variables": [{"name": "pokes", "value": 0}],
    "rules": [
        {"name": "high", "lhs": "x", "cmp": "gt", "rhs": 0.5},
        {"name": "low", "lhs": "x", "cmp": "lt", "rhs": 0.3},
        {"name": "many_pokes", "lhs": "pokes", "cmp": "ge", "rhs": 2},
    ],
    "programs": [
        {"name": "focus", "initial": "idle", "states": {
            "idle": {"next": [{"when": ["high"], "goto": "focusing"}]},
            "focusing": {"every": 0.5,
                                 "next": [{"when": ["low"], "goto": "slipping"}]},
            "slipping": {"do": [{"add": {"name": "pokes", "expr": 1}}],
                                 "next": [{"when": ["many_pokes"], "goto": "idle"},
                                          {"when": ["high"], "goto": "focusing"}]},
        }},
    ],
}


def compiled(tmp_path, config):
    return built(programs_folder(tmp_path, config))


async def step(minutes, x=None, program="focus"):
    if x is not None:
        Stream.registry["x"].value = x
    await tick(T0 + timedelta(minutes=minutes))
    return Program.registry[program].current


async def test_a_program_moves_through_its_states(tmp_path):
    Value("x", 0.0)
    compiled(tmp_path, FOCUS)
    assert await step(0, 0.9) == "idle"  # its first turn: it enters its initial state
    assert await step(1, 0.9) == "focusing"  # a minute later (every): high
    assert await step(2, 0.1) == "slipping"
    assert Stream.registry["pokes"].current() == 1  # slipping's do, on entering
    assert await step(3, 0.9) == "focusing"
    assert await step(4, 0.1) == "slipping"
    assert await step(5, 0.9) == "idle"  # many_pokes comes before high: the first branch that passes


async def test_the_exit_is_tried_every_so_often(tmp_path):
    Value("x", 0.0)
    compiled(tmp_path, FOCUS)
    await step(0, 0.9), await step(1, 0.9)
    assert await step(1.2, 0.1) == "focusing"  # entered 0.2 min ago: every 0.5
    assert await step(1.5, 0.1) == "slipping"
    assert await step(2, 0.5) == "slipping"  # entered at 1.5: not tried yet
    assert await step(2.5, 0.5) == "slipping"  # tried: nothing passes, it stays
    assert await step(3, 0.9) == "slipping"  # next try at 3.5
    assert await step(3.5, 0.9) == "focusing"


async def test_going_to_the_same_state_enters_it_again(tmp_path):
    config = {"variables": [{"name": "ticks", "value": 0}],
              "programs": [{"name": "count", "initial": "idle", "states": {
                  "idle": {"do": [{"add": {"name": "ticks", "expr": 1}}], "next": "idle"}}}]}
    compiled(tmp_path, config)
    for minute in range(4):
        await step(minute, program="count")
    assert Stream.registry["ticks"].current() == 4  # its do, every time it's entered: once a minute


async def test_a_state_with_no_wait_goes_on_at_once_and_is_entered_once_a_cycle():
    from proki.core.programs import State
    from proki.programs.code.base import Ritual, Step, make_branch

    entered = []

    class Mark(Step):
        async def apply(self):
            entered.append(self.program.current)

    class Chain(Ritual):
        def __init__(self):
            super().__init__("@chain", [State(name, do=[Mark(self)], every=timedelta(0), next=[make_branch(goto)])
                                        for name, goto in (("a", "b"), ("b", "a"))])

    Chain()
    await step(0, program="@chain")
    assert entered == ["a", "b"]  # a, then b at once: back to a waits for the next cycle
    await step(1 / 6, program="@chain")
    assert entered == ["a", "b", "a", "b"]


ASK = {"variables": [{"name": "said", "value": 0}],
       "programs": [{"name": "q", "initial": "idle", "states": {
           "idle": {"next": "asking"},
           "asking": {"do": [{"ask_usr": {"title": "Q", "context": {"format": "Start {n}?", "values": {"n": "1 + 1"}},
                                      "options": ["Yes", "No"],
                                      "result": "answer", "default": 1, "timeout": 30}}],
                      "every": 0.1,
                      "next": [{"goto": "yes", "when": "answer == 0"}, {"goto": "no", "when": "answer == 1"}, {"goto": "none", "when": "answer is None"}]},
           "yes": {"do": [{"set": {"name": "said", "expr": 1}}], "next": [{"goto": "yes"}]},
           "no": {"do": [{"set": {"name": "said", "expr": -1}}], "next": [{"goto": "no"}]},
           "none": {"next": "none"}}}]}


async def test_an_answer_picks_the_next_state(tmp_path, ui):
    compiled(tmp_path, ASK)
    await step(0, program="q"), await step(1, program="q")
    assert Program.registry["q"].current == "asking"
    [request] = ui.questions()
    assert (request["context"], ui.labels(request)) == ("Start 2?", ["Yes", "No"])  # values filled in
    assert Stream.registry["q.asking.answer"].current() is None  # waiting: unknown, so no branch passes
    assert Stream.registry["q.asking.answer"].type == "integer"  # what the ask gives: an option's number
    assert await step(1.1, program="q") == "asking"
    await ui.click("Yes")
    assert await step(1.2, program="q") == "yes" and Stream.registry["said"].current() == 1
    assert Stream.registry["q.asking.answer"].current() is None  # the state was left: its variable starts over


async def test_no_answer_in_time_is_nothing_picked(tmp_path, ui):
    config = json.loads(json.dumps(ASK))
    config["programs"][0]["states"]["asking"]["do"][0]["ask_usr"]["timeout"] = 0.05  # seconds
    compiled(tmp_path, config)
    await step(0, program="q"), await step(1, program="q")
    [request] = ui.questions()
    await asyncio.sleep(0.1)  # past its timeout (0.05 s): nothing picked
    assert await step(1.1, program="q") == "none"
    assert ui.sent == [{"type": "cancel", "id": request["id"]}]  # taken off the screen


async def test_nobody_to_ask_is_nothing_picked(tmp_path):
    compiled(tmp_path, ASK)  # nothing answers "proki.ask.usr"
    await step(0, program="q"), await step(1, program="q")
    await settle()
    assert await step(1.1, program="q") == "none"


async def test_a_question_holds_its_program_not_the_others(tmp_path, ui):
    Value("x", 0.0)
    config = {**ASK, "rules": [{"name": "high", "lhs": "x", "cmp": "gt", "rhs": 0.5}]}
    config["programs"] = json.loads(json.dumps(ASK["programs"])) + FOCUS["programs"]
    config["rules"] = FOCUS["rules"]
    config["variables"] = ASK["variables"] + FOCUS["variables"]
    config["programs"][0]["states"]["asking"]["next"].insert(0, {"goto": "no", "when": ["high"]})
    compiled(tmp_path, config)
    await step(0, 0.9, program="q"), await step(1, 0.9, program="q")
    assert await step(1.1, 0.9, program="q") == "asking"  # high, but it waits for the answer
    assert Program.registry["focus"].current == "focusing"  # the other program went on
    await ui.click("Yes")
    assert await step(1.2, 0.9, program="q") == "no"  # answered: now its next, in order


def test_states_are_not_streams(tmp_path):
    Value("x", 0.0)
    config = dict(FOCUS, signals=[{"name": "in_session", "expr": "focus.session"}])
    with pytest.raises(ValueError, match="unknown name 'focus'"):  # a program: no value, so no field of one
        compiled(tmp_path, config)
    other = {"name": "other", "initial": "idle", "variables": [{"name": "seen", "value": "focus.idle"}], "states": {"idle": {}}}
    config = dict(FOCUS, programs=[*FOCUS["programs"], other])
    with pytest.raises(ValueError, match="not allowed in an expression: focus.idle"):  # another program's state: not reached into
        compiled(tmp_path, config)


async def test_a_restart_begins_at_the_initial_state_with_the_variables_kept(tmp_path):
    Variable.store = Memory()
    Value("x", 0.0)
    compiled(tmp_path, FOCUS)
    await step(0, 0.9), await step(1, 0.9), await step(2, 0.1)
    assert Program.registry["focus"].current == "slipping"
    assert Variable.store.saved == {"pokes": 1}  # only variables are kept

    Stream.registry.clear(), Program.registry.clear()  # a restart
    Value("x", 0.0)
    compiled(tmp_path, FOCUS)
    assert Program.registry["focus"].current == "idle"  # back at its initial state
    assert Stream.registry["pokes"].current() == 1  # the variable carries over


def test_programs_are_checked(tmp_path):
    base = FOCUS["rules"][:2]  # high, low: they read x only
    ask = {"ask_usr": {"title": "Q", "context": "?", "options": ["A"], "result": "w", "default": 0}}
    jev = {"ask_jev": {"context": "?", "questions": [{"type": "choice", "question": "Which?", "criteria": {"A": None, "B": None}, "result": "w"}]}}
    asked = lambda **q: {"ask_jev": {"context": "?", "questions": [{**jev["ask_jev"]["questions"][0], **q}]}}
    for states, problem in [
        ({"a": {"colour": 1}}, "unknown colour"),
        ({"a": {"next": [{"when": ["nope"], "goto": "a"}]}}, "unknown name 'nope'"),
        ({"a": {"next": "b"}}, "p has no state 'b'"),
        ({"a": {"next": [{"goto": "a"}, {"when": ["high"], "goto": "a"}]}}, "comes after the else"),
        ({"a": {"next": [{"unless": ["high"], "goto": "a"}]}}, "a branch: unknown unless"),
        ({"a": {"next": "a", "every": -1}}, "every is minutes, 0 or more, or a time"),
        ({"a": {"next": "a", "every": "2m"}}, "every is minutes, 0 or more, or a time"),
        ({"a": {"next": [{"goto": "a", "when": "nope > 1"}]}}, "unknown name 'nope'"),
        ({"a": {"next": [{"goto": "a", "when": 3}]}}, "when is a list of texts"),
        ({"a": {"do": [{"run": "q"}], "next": "a"}}, r"an action is {kind: {params}}"),
        ({"a": {"do": [{"goto": {"state": "a"}}], "next": "a"}}, "an action is one of"),
        ({"a": {"ask_usr": {}, "next": "a"}}, "unknown ask_usr"),
        ({"a": {"do": [{"ask": {"context": "?", "result": "w"}}], "next": "a"}}, "an action is one of"),
        ({"a": {"do": [{"ask_usr": {**ask["ask_usr"], "default": 1}}], "next": "a"}}, "default is an option's index, 0 to 0"),
        ({"a": {"do": [{"ask_usr": {**ask["ask_usr"], "default": -1}}], "next": "a"}}, "default is an option's index, 0 to 0"),
        ({"a": {"do": [{"ask_usr": {**ask["ask_usr"], "default": True}}], "next": "a"}}, "default is an option's index"),
        ({"a": {"do": [{"ask_usr": {**ask["ask_usr"], "default": "nope"}}], "next": "a"}}, "unknown name 'nope'"),
        ({"a": {"do": [{"ask_usr": {**ask["ask_usr"], "default": "1 > 0"}}], "next": "a"}}, "default is an option's index or its text, 1 > 0 gives boolean"),
        ({"a": {"do": [{"ask_usr": {**ask["ask_usr"], "result": "2x"}}], "next": "a"}}, "can't read '2x'"),
        ({"a": {"do": [{"ask_jev": {**jev["ask_jev"], "option": "w"}}], "next": "a"}}, "ask_jev takes .*: unknown option"),
        ({"a": {"do": [{"ask_jev": {**jev["ask_jev"], "title": "A"}}], "next": "a"}}, "ask_jev takes .*: unknown title"),  # only a question to you has one
        ({"a": {"do": [{"ask_usr": {**ask["ask_usr"], "alarm": True}}], "next": "a"}}, "unknown alarm"),  # you're there to answer: only a poke rings
        ({"a": {"do": [asked(type="maybe")], "next": "a"}}, "is a noul, a choice or a score"),
        ({"a": {"do": [asked(type="noul")], "next": "a"}}, "a noul .yes or no. has no criteria"),
        ({"a": {"do": [asked(criteria=None)], "next": "a"}}, "expected a mapping or a sequence"),
        ({"a": {"do": [asked(criteria={"A": None})], "next": "a"}}, "two options or more"),
        ({"a": {"do": [asked(criteria=[{"option": "A"}, "B"])], "next": "a"}}, "invalid choice option"),
        ({"a": {"do": [asked(question="")], "next": "a"}}, "asks something: a text"),
        ({"a": {"do": [asked(colour=1)], "next": "a"}}, "a question takes {type, question, criteria, result}: unknown colour"),
        ({"a": {"do": [{"ask_jev": {"context": "?", "questions": [{"type": "noul", "question": "Yes?"}]}}], "next": "a"}}, "a question takes .*: missing result"),
        ({"a": {"do": [{"ask_jev": {"context": "?", "questions": [jev["ask_jev"]["questions"][0]] * 2}}], "next": "a"}}, "a variable of its own"),
        ({"a": {"do": [{"ask_usr": {**ask["ask_usr"], "options": None}}], "next": "a"}}, "default is an option, so it needs options"),
        ({"a": {"next": "a"}, "b.c": {"next": "a"}}, "p.b.c: state name .b.c.: a name is letters"),
        ({"a": {"do": [{"ask_usr": {k: v for k, v in ask["ask_usr"].items() if k != "result"}}], "next": "a"}}, "missing result"),
        ({"a": {"do": [{"ask_usr": {k: v for k, v in ask["ask_usr"].items() if k != "title"}}], "next": "a"}}, "missing title"),
        ({"a": {"do": [{"ask_usr": {**ask["ask_usr"], "title": ""}}], "next": "a"}}, "title is a text"),
        ({"a": {"do": [{"ask_usr": {**ask["ask_usr"], "options": [{"option": "A"}]}}], "next": "a"}}, "an option is a text"),
        ({"a": {"do": [{"ask_usr": {**ask["ask_usr"], "options": ["A", "A"]}}], "next": "a"}}, "listed twice"),
        ({"a": {"do": [{"ask_usr": {**ask["ask_usr"], "options": "nope"}}], "next": "a"}}, "unknown name 'nope'"),
        ({"a": {"do": [{"ask_llm": {"context": "?", "result": "w", "schema": "number"}}], "next": "a"}}, "unknown schema"),
        ({"a": {"do": [{"ask_llm": {"context": "?", "result": "w", "options": ["A"]}}], "next": "a"}}, "unknown options"),
        ({"a": {"do": [{"ask_usr": {**ask["ask_usr"], "context": {"format": "{n}", "values": {"n": "nope"}}}}], "next": "a"}}, "unknown name 'nope'"),
        ({"a": {"do": [{"ask_usr": {**ask["ask_usr"], "context": {"format": "?", "values": ["v"]}}}], "next": "a"}}, "context's values are"),
        ({"a": {"do": [{"ask_usr": {**ask["ask_usr"], "context": ""}}], "next": "a"}}, "context's format is"),
        ({"a": {"do": [{"ask_usr": {**ask["ask_usr"], "context": {"format": "?", "colour": 1}}}], "next": "a"}}, "context is a text, or {format, values}"),
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


async def test_the_shipped_day_program_moves_its_deadline_at_midnight():
    from proki.services.activitywatch import Record

    built(settings.SHIPPED_DIR)
    deadline = Stream.registry["deadline_eod"]
    midnight = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    before, after = midnight - timedelta(minutes=2), midnight + timedelta(minutes=2)
    Stream.now = before
    replay(before + timedelta(minutes=1), Record.of(before, after, {}))
    Program.tick(Stream.now)
    await settle()
    assert deadline.current() == pytest.approx(midnight.timestamp() / 60)  # the next midnight
    replay(after, Record.of(before, after, {}))
    Program.tick(Stream.now)
    await settle()
    assert deadline.current() == pytest.approx(midnight.timestamp() / 60 + 1440)  # passed: the one after
    Program.tick(Stream.now + timedelta(minutes=5))
    await settle()
    assert deadline.current() == pytest.approx(midnight.timestamp() / 60 + 1440)  # once


async def test_names_are_found_from_the_state_outwards(tmp_path):
    Variable.store = Memory()
    config = {
        "variables": [{"name": "count", "value": 1}],
        "programs": [{"name": "p", "initial": "a", "variables": [{"name": "total", "value": "count + 1"}], "states": {
            "a": {"variables": [{"name": "mine", "value": 5}],
                  "do": [{"set": {"name": "total", "expr": "total + mine + count"}}], "next": "b"},
            "b": {"do": [{"set": {"name": "count", "expr": "total"}}], "next": "b"},
        }}],
    }
    compiled(tmp_path, config)
    assert {"count", "p.total", "p.a.mine"} <= set(Stream.registry)  # each under its full name
    await step(0, program="p")
    assert Stream.registry["p.total"].current() == 2 + 5 + 1  # a's own, the program's, the global one
    await step(1, program="p")
    assert Stream.registry["count"].current() == 8  # b sets the global one to the program's
    assert Variable.store.saved == {"count": 8}  # only a global one is kept (a program's lives as long as it)


def test_a_state_cant_see_another_states_variables(tmp_path):
    """b sets a `mine` of its own: a's is a's."""
    config = {"programs": [{"name": "p", "initial": "a", "states": {
        "a": {"variables": [{"name": "mine", "value": 5}], "next": "b"},
        "b": {"do": [{"set": {"name": "mine", "expr": 1}}], "next": "b"},
    }}]}
    compiled(tmp_path, config)
    assert {"p.a.mine", "p.b.mine"} <= set(Stream.registry)
    assert Stream.registry["p.a.mine"].current() == 5


def test_a_set_makes_its_variable_an_add_needs_one(tmp_path):
    """A set only writes its variable: one that's nobody's is its state's own. An add reads it too."""
    state = lambda do: {"programs": [{"name": "p", "initial": "a", "states": {"a": {"do": [do], "next": "a"}}}]}
    compiled(tmp_path, state({"set": {"name": "fresh", "expr": 1}}))
    assert "p.a.fresh" in Stream.registry
    Stream.registry.clear()
    with pytest.raises(ValueError, match="add: no variable is called 'p.a.fresh'"):
        compiled(tmp_path, state({"add": {"name": "fresh", "expr": 1}}))


def test_an_action_reads_what_is_there_and_sets_a_new_name_alone(tmp_path):
    """As in Python: x := x + 1 needs an x already; a new name is a name alone, not a place in one."""
    state = lambda *do: {"variables": [{"name": "names", "value": "['walk']", "type": {"type": "array", "items": {"type": "string"}}}],
                         "programs": [{"name": "p", "initial": "a", "states": {"a": {"do": list(do), "next": "a"}}}]}
    for do, problem in [({"set": {"name": "fresh", "expr": "fresh + 1"}}, "unknown name 'fresh'"),
                        ({"set": {"name": "fresh.a", "expr": "1"}}, "no variable is called 'fresh.a'"),
                        ({"set": {"name": "fresh[0]", "expr": "1"}}, "no variable is called")]:
        Stream.registry.clear()
        with pytest.raises(ValueError, match=problem):
            compiled(tmp_path, state(do))
    Stream.registry.clear()
    compiled(tmp_path, state({"ask_llm": {"context": "What's it called?", "result": "names[0]"}},  # an answer into a place
                             {"set": {"name": "seen", "expr": "names[0]"}}))
    assert "p.a.seen" in Stream.registry and "p.a.names" not in Stream.registry
    with pytest.raises(ValueError, match="names\\[0\\] is of type string: the answer is integer"):
        compiled(tmp_path, state({"ask_usr": {"title": "Q", "context": "Which?", "options": ["A", "B"], "result": "names[0]"}}))



def test_a_value_of_another_type_is_refused_as_the_programs_are_built(tmp_path):
    """Every type is worked out once all is made: what an action sets is checked then, not as it runs."""
    for do, problem in [({"set": {"name": "count", "expr": "'many'"}}, "set: count is of type number, 'many' gives string"),
                        ({"add": {"name": "seen", "expr": 1}}, "add: adds and subtracts numbers"),
                        ({"set": {"name": "seen", "expr": "count > 3"}}, None),  # a yes or no: fine
                        ({"add": {"name": "count", "expr": "seen"}}, None),  # yes: 1
                        ({"set": {"name": "count", "expr": "count * 2 + 1"}}, None)]:
        config = {"variables": [{"name": "count", "value": 0}, {"name": "seen", "value": False}],
                  "programs": [{"name": "p", "initial": "a", "states": {"a": {"do": [do], "next": "a"}}}]}
        Stream.registry.clear()
        if problem is None:
            compiled(tmp_path, config)
            assert Stream.registry["count"]._typed == "number" and Stream.registry["seen"]._typed == "boolean"  # kept, not worked out again
        else:
            with pytest.raises(ValueError, match=problem):
                compiled(tmp_path, config)


def test_one_variable_answered_two_ways_is_refused(tmp_path):
    asks = [{"ask_usr": {"title": "Q", "context": "Which?", "options": ["a", "b"], "result": "said"}},  # an option's index
            {"ask_usr": {"title": "Q", "context": "What?", "result": "said"}}]                           # a text
    config = {"programs": [{"name": "p", "initial": "a", "states": {"a": {"do": asks, "next": "a"}}}]}
    with pytest.raises(ValueError, match="answered as integer already: this answer is string"):
        compiled(tmp_path, config)

def test_a_jump_stays_in_its_own_program(tmp_path):
    Value("x", 0.9)
    config = {"rules": FOCUS["rules"][:1], "programs": [
        {"name": "p", "initial": "a", "states": {"a": {"next": "a"}}},
        {"name": "q", "initial": "b", "states": {"b": {"next": [{"when": ["high"], "goto": "a"}]}}},
    ]}
    with pytest.raises(ValueError, match="q has no state 'a'"):  # a is p's
        compiled(tmp_path, config)


async def test_a_poke_is_a_notice(tmp_path, ui):
    config = {"programs": [{"name": "p", "initial": "idle", "states": {
        "idle": {"do": [{"poke": {"context": {"format": "{n} left", "values": {"n": "2 * 3"}}}}], "next": [{"goto": "done"}]},
        "done": {"next": [{"goto": "done"}]}}}]}
    compiled(tmp_path, config)
    await step(0, program="p")
    assert ui.sent == [{"type": "poke", "text": "6 left"}] and ui.requests == []  # one way: nothing to answer


NOTE = {"programs": [{"name": "capture", "initial": "idle", "variables": [{"name": "note"}], "states": {
    "idle": {"next": "asking"},
    "asking": {"do": [{"ask_usr": {"title": "Q", "context": "Anything worth noting?", "result": "text"}},
                      {"set": {"name": "note", "expr": "text"}}],
               "every": 0.1,
               "next": [{"goto": "classifying", "when": "text"}, {"goto": "idle"}]},
    "classifying": {"do": [{"ask_jev": {"context": {"format": "A note someone wrote: {note}", "values": {"note": "note"}},
                                        "questions": [{"type": "choice", "question": "What is it?", "result": "kind",
                                                       "criteria": {"todo": "something to do later", "thought": None}}]}}],
                    "every": 0.1,
                    "next": [{"goto": "adding", "when": ["kind.index == 0", "kind.conf > 0.5"]}, {"goto": "idle"}]},
    "adding": {"do": [{"poke": {"context": {"format": "Added “{note}” to your tasks", "values": {"note": "note"}}}}], "next": "adding"}}}]}


class FakeJev:
    def __init__(self, choice):
        self.choice, self.asked = choice, []

    def ask(self, state, questions):
        self.asked.append(state)
        answer = {"noul":   lambda q: {"noul": 0.9},
                  "choice": lambda q: {"choice": list(q["criteria"])[self.choice], "probabilities": {list(q["criteria"])[self.choice]: 0.9}, "confidence": 0.9},
                  "score":  lambda q: {"score": 1.9, "probabilities": {"1": 0.2, "2": 0.8}, "confidence": 0.8}}
        return {name: answer[q["type"]](q) for name, q in questions.items()}


async def test_a_typed_note_goes_on_to_jev_and_through_the_program_to_the_next_state(tmp_path, ui):
    from proki.channels import Channels, jev
    fake = FakeJev(0)
    await jev.serve(Channels.bus, fake)
    compiled(tmp_path, NOTE)
    await step(0, program="capture"), await step(1, program="capture")
    assert ui.labels(ui.questions()[-1]) is None  # no options: a text to type
    await ui.click("buy milk")
    assert await step(1.2, program="capture") == "classifying"
    await settle()
    assert fake.asked == ["A note someone wrote: buy milk"]  # the program's note, filled into jev's question
    assert await step(1.4, program="capture") == "adding"
    await settle()
    assert {"type": "poke", "text": "Added “buy milk” to your tasks"} in ui.sent


async def test_no_text_goes_back_to_idle_without_asking_jev(tmp_path, ui):
    from proki.channels import Channels, jev
    fake = FakeJev(0)
    await jev.serve(Channels.bus, fake)
    compiled(tmp_path, NOTE)
    await step(0, program="capture"), await step(1, program="capture")
    await ui.click(None)  # skipped: no note
    assert await step(1.2, program="capture") == "idle"  # "text" is unknown: not true
    assert fake.asked == []


async def test_each_program_has_its_own_answer(tmp_path, ui):
    one = json.loads(json.dumps(ASK["programs"][0]))
    two = {**json.loads(json.dumps(one)), "name": "r"}
    compiled(tmp_path, {**ASK, "programs": [one, two]})
    await step(0, program="q"), await step(1, program="q")
    q_asked, r_asked = ui.questions()
    await ui.click("Yes", q_asked)
    await ui.click("No", r_asked)
    assert Stream.registry["q.asking.answer"].current() == 0 and Stream.registry["r.asking.answer"].current() == 1
    await step(1.2, program="q")
    assert (Program.registry["q"].current, Program.registry["r"].current) == ("yes", "no")


def test_rules_and_signals_see_only_the_global_scope(tmp_path):
    states = {"a": {"do": [{"ask_usr": {"title": "Q", "context": "?", "options": ["A"], "result": "answer"}}],
                    "next": [{"goto": "a", "when": ["said_a"]}]}}
    with pytest.raises(ValueError, match="unknown name 'answer'"):
        compiled(tmp_path, {"rules": [{"name": "said_a", "lhs": "answer", "cmp": "eq", "rhs": 0}],
                            "programs": [{"name": "p", "initial": "a", "states": states}]})


async def test_programs_and_states_have_rules_of_their_own(tmp_path, ui):
    config = {"rules": [{"name": "always", "lhs": 1, "cmp": "eq", "rhs": 1}],
              "programs": [{"name": "q", "initial": "asking",
                            "variables": [{"name": "asked", "value": 0}],
                            "rules": [{"name": "asked_before", "lhs": "asked", "cmp": "ge", "rhs": 1}],
                            "states": {
        "asking": {"do": [{"add": {"name": "asked", "expr": 1}},
                          {"ask_usr": {"title": "Q", "context": "?", "options": ["Yes", "No"],
                                   "result": "answer"}}],
                   "rules": [{"name": "said_yes", "lhs": "answer", "cmp": "eq", "rhs": 0}],
                   "every": 0.1,
                   "next": [{"goto": "yes", "when": ["said_yes", "asked_before", "always"]}, {"goto": "asking"}]},
        "yes": {"next": "yes"}}}]}
    compiled(tmp_path, config)
    assert {"q.asked_before", "q.asking.said_yes", "always"} <= set(Rule.registry)  # each under its full name
    assert [r.name for r in Program.registry["q"].rules] == ["q.asked_before"]
    assert [r.name for r in Program.registry["q"].states["asking"].rules] == ["q.asking.said_yes"]
    await step(0, program="q")
    await ui.click("Yes")
    assert await step(0.1, program="q") == "yes"  # the state's rule, the program's, the global one


def test_scoped_rules_are_checked(tmp_path):
    rule = {"name": "r", "lhs": 1, "cmp": "eq", "rhs": 1}
    for program, problem in [
        ({"rules": [rule, rule]}, "'r' is defined twice"),
        ({"variables": [{"name": "r"}], "rules": [rule]}, "'r' is defined twice"),
        ({"rules": [{**rule, "colour": 1}]}, "rule 'r': unknown colour"),
        ({"states": {"a": {"next": [{"goto": "a", "when": ["other"]}]}}}, "unknown name 'other'"),
    ]:
        Stream.registry.clear(), Program.registry.clear(), Rule.registry.clear()
        spec = {"name": "p", "initial": "a", "states": {"a": {"next": "a"}}, **program}
        with pytest.raises(ValueError, match=problem):
            compiled(tmp_path, {"rules": [{**rule, "name": "g"}], "programs": [spec]})


async def test_a_branch_can_mix_rules_and_conditions(tmp_path):
    Value("x", 0.9)
    config = {"rules": FOCUS["rules"][:1], "variables": [{"name": "n", "value": 0}],
              "programs": [{"name": "p", "initial": "a", "states": {
                  "a": {"do": [{"add": {"name": "n", "expr": 1}}],
                        "next": [{"goto": "b", "when": ["high", "n >= 2", "x > 0.5"]}, {"goto": "a"}]},
                  "b": {"next": "b"}}}]}
    compiled(tmp_path, config)
    branch = Program.registry["p"].states["a"].next[0]
    assert ([r.name for r in branch.rules], len(branch.conds)) == (["high"], 2)  # a rule, and two conditions
    assert [await step(m, program="p") for m in (0, 1, 2)] == ["a", "a", "b"]  # every condition true, then the rule


async def test_a_state_without_next_goes_back_to_the_initial_state(tmp_path):
    config = {"programs": [{"name": "p", "initial": "start", "states": {"start": {"next": "end"}, "end": {}}}]}
    compiled(tmp_path, config)
    assert [await step(m, program="p") for m in (0, 1, 2)] == ["start", "end", "start"]


def test_a_program_name_is_a_plain_name():
    from proki.core.programs import State
    for name in ["2nd", "a.b", "é", "a-b", ""]:
        with pytest.raises(ValueError, match="a name is ASCII letters, digits and _"):
            Program(name, {"s": State("s")}, "s")


async def test_a_programs_variables_live_as_long_as_it(tmp_path):
    """A state's start over when it's left, a program's when it starts over. Only a global
    one is kept across restarts."""
    config = {"programs": [{"name": "p", "initial": "a", "variables": [{"name": "runs", "value": 0}], "states": {
                  "a": {"variables": [{"name": "here", "value": 0}],
                        "do": [{"add": {"name": "here", "expr": 1}}, {"add": {"name": "runs", "expr": 1}}],
                        "every": 1, "next": [{"goto": "b", "when": "here >= 1"}]},
                  "b": {"every": 1, "next": "b"}}}]}
    compiled(tmp_path, config)
    await step(0, program="p")
    assert Stream.registry["p.a.here"].current() == 1 and Stream.registry["p.runs"].current() == 1
    await step(1, program="p")
    assert Program.registry["p"].current == "b" and Stream.registry["p.a.here"].current() == 0  # a was left: its variable started over
    program = Program.registry["p"]
    program.switch(False), program.switch(True)
    await step(2, program="p")
    assert Stream.registry["p.runs"].current() == 1  # started over, then a counted once
    assert not program.vars[0].persist and not program.states["a"].vars[0].persist


async def test_a_question_no_longer_asked_leaves_the_screen(tmp_path, ui):
    """Its program switched off (or moved on): the question goes."""
    config = {"programs": [{"name": "p", "initial": "idle", "states": {
        "idle": {"do": [{"ask_usr": {"title": "Q", "context": "Up?", "options": ["Yes"],
                                  "result": "answer"}}], "next": "idle"}}}]}
    compiled(tmp_path, config)
    await step(0, program="p")
    [asked] = ui.questions()
    Program.registry["p"].switch(False)
    await settle()
    assert {"type": "cancel", "id": asked["id"]} in ui.sent


async def test_a_name_declared_inside_hides_the_one_around_it(tmp_path, ui):
    """As in Python: the state's `n` is found before the program's, the program's before the
    global one, and each keeps its own value."""
    config = {"variables": [{"name": "n", "value": 1}],
              "programs": [{"name": "p", "initial": "a", "variables": [{"name": "n", "value": 10}], "states": {
                  "a": {"variables": [{"name": "n", "value": 100}], "do": [{"add": {"name": "n", "expr": "n"}}], "next": "b"},
                  "b": {"do": [{"add": {"name": "n", "expr": "n"}}], "next": "b"}}}]}
    compiled(tmp_path, config)
    await step(0, program="p")
    assert Stream.registry["p.a.n"].current() == 200 and Stream.registry["p.n"].current() == 10  # a's own
    await step(1, program="p")
    assert Stream.registry["p.n"].current() == 20 and Stream.registry["n"].current() == 1  # b sees the program's


async def test_programs_and_states_have_signals_of_their_own(tmp_path, ui):
    """A program's signal reads its variables, a state's reads its own too, each under its full
    name, and a branch or a rule finds them from inside like any name."""
    config = {"variables": [{"name": "count", "value": 1}],
              "programs": [{"name": "p", "initial": "a", "variables": [{"name": "n", "value": 2}],
                            "signals": [{"name": "twice", "expr": "n * 2"}], "states": {
                  "a": {"variables": [{"name": "m", "value": 5}], "signals": [{"name": "sum", "expr": "m + twice + count"}],
                        "rules": [{"name": "big", "lhs": "sum", "cmp": "gt", "rhs": 9}],
                        "next": [{"goto": "b", "when": ["big", "twice == 4"]}]},
                  "b": {"next": "b"}}}]}
    compiled(tmp_path, config)
    assert {"p.twice", "p.a.sum"} <= set(Stream.registry) and "twice" not in Stream.registry
    await step(0, program="p")
    assert Stream.registry["p.a.sum"].current() == 10  # 5 + 4 + 1
    assert await step(1, program="p") == "b"
    Stream.registry.clear(), Program.registry.clear(), Rule.registry.clear()
    with pytest.raises(ValueError, match="unknown name 'twice'"):  # a program's own isn't seen from outside
        compiled(tmp_path, {**config, "signals": [{"name": "outside", "expr": "twice + 1"}]})


async def test_a_poke_draws_from_its_picks(tmp_path, ui):
    Popup.lib.set_picks("hi", ["bugcat/sad", "alarm-clock"])
    config = {"programs": [{"name": "p", "initial": "idle", "states": {
        "idle": {"do": [{"id": "hi", "poke": {"context": "Hi"}}, {"poke": {"context": "Nothing"}}]}}}]}
    compiled(tmp_path, config)
    await step(0, program="p")
    picked, plain = [m for m in ui.sent if m["type"] == "poke"]
    assert picked["media"].endswith("bugcat/sad.gif") and picked["sound"].endswith("alarm-clock.mp3")
    assert "media" not in plain and "sound" not in plain  # no picks: none


async def test_a_question_has_its_own_pictures_and_sounds_along_with_the_pool(tmp_path, ui):
    Popup.lib.set_pool("questions", [])  # only its own, to see which is drawn
    Popup.lib.set_picks("up", ["bugcat/sad", "alarm-clock"])
    config = {"programs": [{"name": "p", "initial": "idle", "states": {
        "idle": {"do": [{"id": "up", "ask_usr": {"title": "Up", "context": "Up?", "options": ["Yes"], "result": "answer"}}], "next": "idle"}}}]}
    compiled(tmp_path, config)
    await step(0, program="p")
    [asked] = ui.questions()
    assert asked["show"]["title"] == "Up" and asked["show"]["media"].endswith("bugcat/sad.gif")
    assert asked["show"]["sound"].endswith("alarm-clock.mp3") and "immediate" not in asked["show"]  # "Later" too
    Program.registry["p"].switch(False)
    await settle()


async def test_an_immediate_question_is_to_answer_now(tmp_path, ui):
    config = {"programs": [{"name": "p", "initial": "idle", "states": {
        "idle": {"do": [{"ask_usr": {"title": "Q", "context": "Up?", "options": ["Yes"], "result": "answer",
                                 "immediate": True}}], "next": "idle"}}}]}
    compiled(tmp_path, config)
    await step(0, program="p")
    [asked] = ui.questions()
    assert asked["show"]["immediate"] is True  # no "Later"
    Program.registry["p"].switch(False)
    await settle()


async def test_the_llms_object_is_read_by_its_fields_and_jevs_answer_with_how_sure(tmp_path, ui):
    from proki.channels import Channels, jev, llm

    class Saying:
        def ask(self, prompt, schema=None):
            self.schema = schema
            return {"people": 3, "hours": 1.5}

    said = Saying()
    await llm.serve(Channels.bus, said)
    await jev.serve(Channels.bus, FakeJev(1))
    config = {"programs": [{"name": "p", "initial": "idle", "states": {
        "idle": {"next": "asking"},
        "asking": {"variables": [{"name": "need", "value": None, "type": {"type": "object", "properties": {"people": {"type": "number"}, "hours": {"type": "number"}}}}],
                   "do": [{"ask_llm": {"context": "Who's needed?", "result": "need"}},  # answered in its variable's type
                          {"ask_jev": {"context": "A job.", "questions": [
                              {"type": "choice", "question": "Is it big?", "criteria": {"small": None, "big": None}, "result": "size"},
                              {"type": "noul", "question": "Is it today's?", "result": "today"},
                              {"type": "score", "question": "How hard?", "criteria": {"0": "easy", "1": "hard", "2": "very hard"}, "result": "hard"}]}}],
                   "every": 0.1,
                   "next": [{"goto": "big", "when": ["need.people * need.hours > 4", "size.index == 1", "size.conf > 0.5",
                                                     "today >= 0.5", "hard.score > 1.5", "hard.conf > 0.5"]},
                            {"goto": "idle"}]},
        "big": {"next": "big"}}}]}
    compiled(tmp_path, config)
    await step(0, program="p"), await step(1, program="p")
    for _ in range(100):  # the workers answer on threads
        if Stream.registry["p.asking.size"].current() is not None:  break
        await asyncio.sleep(0.01)
    assert said.schema["required"] == ["people", "hours"] and Stream.registry["p.asking.need"].current() == {"people": 3, "hours": 1.5}
    assert Stream.registry["p.asking.size"].current() == {"index": 1, "conf": 0.9, "odds": [0.0, 0.9]}  # each option's too
    assert Stream.registry["p.asking.today"].current() == 0.9  # a yes or no: the probability of yes
    assert Stream.registry["p.asking.hard"].current() == {"score": 1.8, "conf": 0.8, "odds": [0.0, 0.2, 0.8]}  # 0.2 at 1, 0.8 at 2: 1.8
    assert await step(1.2, program="p") == "big"


def test_a_global_name_can_have_a_dot(tmp_path):
    config = {"variables": [{"name": "session.active", "value": True}, {"name": "pokes", "value": 0}],
              "signals": [{"name": "session.on", "expr": "session.active and pokes == 0"}],
              "programs": [{"name": "p", "initial": "a", "states": {"a": {"next": [{"goto": "a", "when": ["session.on"]}]}}}]}
    compiled(tmp_path, config)
    Stream.now = T0
    assert Stream.registry["session.on"].current() is True
    for bad, problem in [({"name": "a.b.c", "value": 1}, "a name is letters")]:
        Stream.registry.clear(), Program.registry.clear()
        with pytest.raises(ValueError, match=problem):
            compiled(tmp_path, {**config, "variables": [*config["variables"], bad]})


def test_a_time_is_minutes_or_a_phrase(tmp_path):
    Value("x", 0.0)
    config = dict(FOCUS, signals=[{"name": "kept", "expr": "x", "backfill": "1d"}])
    config["programs"] = [{**FOCUS["programs"][0], "states": {**FOCUS["programs"][0]["states"],
                                                             "idle": {"every": "6s", "next": [{"when": ["high"], "goto": "focusing"}]}}}]
    compiled(tmp_path, config)
    assert Program.registry["focus"].states["idle"].every == timedelta(seconds=6)
    assert Stream.registry["kept"].window == timedelta(days=1)


def test_what_a_program_reads_and_sets_is_said_by_its_actions_and_ways_out(tmp_path):
    config = {"variables": [{"name": "x", "value": 0}, {"name": "y", "value": 0}, {"name": "z", "value": 0}],
              "programs": [{"name": "p", "initial": "a", "states": {
                  "a": {"do": [{"set": {"name": "x", "expr": "y + 1"}}], "next": [{"goto": "a", "when": ["x > 3"]}, {"goto": "a"}]}}}]}
    compiled(tmp_path, config)
    p = Program.registry["p"]
    action = p.states["a"].do[0]
    assert action.read() == ["y + 1"] and [v.name for v in action.write()] == ["x"]
