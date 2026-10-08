import json
from datetime import datetime, timedelta, timezone

import pytest

from conftest import replay_cycle, settle
from proki.compiler import compile_config
from proki.core.programs import Program
from proki.core.ask import Asking, ask_jev, ask_llm, ask_usr, waiting
from proki.core.signals import Stream
from proki.engine import Engine, serve_jev, serve_llm
from proki.engine.workers import pick
from proki.services.activitywatch import Record

T0 = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)


def at(minutes):
    return T0 + timedelta(minutes=minutes)


SUGGEST = {
    "variables": [{"name": "session", "value": False}, {"name": "shallow", "value": 42},
                  {"name": "last_asked", "value": 0}, {"name": "answer", "value": -2}],
    "programs": [{"name": "suggest", "initial": "asking", "states": {
        "asking": {"do": [{"set": {"name": "last_asked", "expr": "time"}},
                          {"ask": {"channel": "usr", "context": "{minutes} min shallow ({hours:.1f} h). Start?",
                                   "values": {"minutes": "shallow", "hours": "shallow / 60"},
                                   "options": [{"option": "Start"}, {"option": "Not now"}],
                                   "result": "answer", "default": 1}}],
                   "every": 0.1,
                   "next": [{"goto": "started", "if": "answer == 0"}, {"goto": "idle", "if": "answer == 1"}]},
        "started": {"do": [{"set": {"name": "session", "expr": True}}], "next": "started"},
        "idle": {"do": [{"set": {"name": "last_asked", "expr": -1}}], "next": "idle"}}}],
}


def engine(tmp_path, config, **kwargs):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    return Engine(path, **kwargs)


def cycle(e, minutes):
    replay_cycle(e, at(minutes), rec=Record.of(at(minutes) - timedelta(minutes=1), at(minutes), {}))


def test_an_answer_is_acted_on_at_the_next_cycle(tmp_path, ui):
    e = engine(tmp_path, {"inputs": [{"name": "time"}], **SUGGEST})
    cycle(e, 0)
    [request] = ui.questions(1)
    assert (request["context"], request["options"]) == ("42 min shallow (0.7 h). Start?", [["Start", None], ["Not now", None]])
    assert waiting("usr") == 1
    ui.click("Start")
    assert Stream.registry["session"].value is False  # not yet: answers wait for the engine's turn
    cycle(e, 1)
    assert Stream.registry["session"].value is True and waiting("usr") == 0


def test_no_answer_is_the_default_option(tmp_path, ui):
    e = engine(tmp_path, {"inputs": [{"name": "time"}], **SUGGEST})
    cycle(e, 0)
    ui.click(None)  # dismissed
    cycle(e, 1)
    assert Stream.registry["last_asked"].value == -1 and Stream.registry["session"].value is False


def test_nobody_to_ask_is_the_default_option(tmp_path):
    e = engine(tmp_path, {"inputs": [{"name": "time"}], **SUGGEST})  # nothing answers "proki.ask.usr"
    cycle(e, 0)
    settle()
    cycle(e, 1)
    assert Stream.registry["last_asked"].value == -1


def test_a_question_too_late_is_taken_off_the_ui(ui):
    assert ask_usr("Start?", ["Start", "Not now"], timeout=0.05) is None
    assert ui.sent == [{"type": "cancel", "id": ui.requests[0]["id"]}]


class FakeJev:
    def __init__(self, choice):
        self.choice, self.asked = choice, None

    def ask(self, state, questions):
        self.asked = (state, questions)
        return {"answer": {"choice": self.choice}}


def test_jev_chooses_among_the_options():
    jev = FakeJev("o1")
    serve_jev(Asking.bus, jev)
    assert ask_jev("github.com", [("deep", "coding"), "shallow"]) == 1
    assert jev.asked[1]["answer"]["criteria"] == {"o0": "coding", "o1": "shallow"}
    serve_jev(Asking.bus, FakeJev("nope"))
    Asking.bus.handlers["proki.ask.jev"].pop(0)
    assert ask_jev("github.com", ["deep", "shallow"]) is None  # not one of the options


class FakeLlm:
    def __init__(self, reply):
        self.reply, self.prompt = reply, None

    def complete(self, prompt):
        self.prompt = prompt
        return self.reply

    def ask(self, prompt, schema=None):
        self.prompt = prompt
        return {"minutes": 30}


def test_an_llm_picks_an_option_writes_json_or_text():
    llm = FakeLlm(' "Not now". ')
    serve_llm(Asking.bus, llm)
    assert ask_llm("Start?", ["Start", "Not now"]) == 1 and "- Start\n- Not now" in llm.prompt
    assert ask_llm("How long?", schema={"type": "object"}) == {"minutes": 30}
    assert ask_llm("Say hi") == ' "Not now". '
    assert pick("maybe later", ["Start", "Not now"]) is None


def test_nobody_answers_a_channel_without_a_worker():
    assert ask_jev("github.com", ["deep", "shallow"]) is None and ask_llm("hi") is None


def test_the_config_cant_name_a_program_in_code(tmp_path):
    from proki.programs import Ritual

    config = {"programs": [{"name": "plan", "initial": "s", "states": {"s": {}}}]}
    with pytest.raises(ValueError, match="a program in proki's code"):
        engine(tmp_path, config, programs=[lambda: Ritual("plan")])
