from datetime import datetime, timedelta, timezone

import pytest

from conftest import programs_folder, replay_cycle, settle
from proki.core.programs import Program
from proki.channels import Channels, jev as jev_channel, llm as llm_channel, queued
from proki.channels.jev import JevQuestion
from proki.channels.llm import LLMQuestion
from proki.core.signals import Stream
from proki.engine import Engine
from proki.services.activitywatch import Record

T0 = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)


def at(minutes):
    return T0 + timedelta(minutes=minutes)


SUGGEST = {
    "variables": [{"name": "session", "value": False}, {"name": "shallow", "value": 42},
                  {"name": "last_asked", "value": 0}],
    "programs": [{"name": "suggest", "initial": "asking", "states": {
        "asking": {"do": [{"set": {"name": "last_asked", "expr": "time"}},
                          {"ask_usr": {"title": "Q", "context": {"format": "{minutes} min shallow ({hours:.1f} h). Start?",
                                                                 "values": {"minutes": "shallow", "hours": "shallow / 60"}},
                                   "options": ["Start", "Not now"],
                                   "result": "answer", "default": 1}}],
                   "every": 0.1,
                   "next": [{"goto": "started", "when": "answer == 0"}, {"goto": "idle"}]},
        "started": {"do": [{"set": {"name": "session", "expr": True}}], "next": "started"},
        "idle": {"do": [{"set": {"name": "last_asked", "expr": -1}}], "next": "idle"}}}],
}


def engine(tmp_path, config, **kwargs):
    return Engine(programs_folder(tmp_path, config), **kwargs)


async def cycle(e, minutes):
    await replay_cycle(e, at(minutes), rec=Record.of(at(minutes) - timedelta(minutes=1), at(minutes), {}))
    await settle()  # a question just asked reaches the UI


async def test_an_answer_is_acted_on_at_the_next_cycle(tmp_path, ui):
    e = engine(tmp_path, {"inputs": [{"name": "time"}], **SUGGEST})
    await cycle(e, 0)
    [request] = ui.questions()
    assert (request["context"], request["options"]) == ("42 min shallow (0.7 h). Start?", [["Start", None], ["Not now", None]])
    assert queued("usr") == 1
    await ui.click("Start")
    assert Stream.registry["session"].value is False  # not yet: the program moves on at its next turn
    await cycle(e, 1)
    assert Stream.registry["session"].value is True and queued("usr") == 0


async def test_its_default_is_the_option_picked_already(tmp_path, ui):
    asking = SUGGEST["programs"][0]["states"]["asking"]
    ask = {"ask_usr": {**asking["do"][1]["ask_usr"], "default": "'Not now' if shallow > 30 else 0"}}
    config = {**SUGGEST, "programs": [{**SUGGEST["programs"][0], "states": {**SUGGEST["programs"][0]["states"], "asking": {**asking, "do": [asking["do"][0], ask]}}}]}
    e = engine(tmp_path, {"inputs": [{"name": "time"}], **config})
    await cycle(e, 0)
    [request] = ui.questions()
    assert request["show"]["selected"] == 1  # by its text


class FakeJev:
    def __init__(self, choice):
        self.choice, self.asked = choice, None   # the option it picks, by its place

    def ask(self, state, questions):
        self.asked = (state, questions)
        picked = lambda q: list(q["criteria"])[self.choice]
        return {name: {"choice": picked(q), "probabilities": {picked(q): 0.9}, "confidence": 0.9} for name, q in questions.items()}


async def test_jev_answers_its_questions_with_their_probabilities():
    await jev_channel.serve(Channels.bus, jev := FakeJev(0))
    questions = {"size": {"type": "choice", "question": "How long?", "criteria": {"short": "<25 min", "long": ">2 h"}}}
    assert await JevQuestion("write the intro", questions).invoke() == {"size": {"index": 0, "conf": 0.9, "odds": [0.9, 0.0]}}
    assert jev.asked == ("write the intro", {"size": {"type": "choice", "instructions": "How long?",
                                                      "criteria": {"short": "<25 min", "long": ">2 h"}}})  # as jev takes it


class FakeLlm:
    def __init__(self, reply):
        self.reply, self.prompt = reply, None

    def ask(self, prompt, schema=None):
        self.prompt, self.schema = prompt, schema
        if schema is None:
            return self.reply
        return {"minutes": 30}


async def test_an_llm_writes_json_or_text_and_an_ask_of_it_keeps_its_answer():
    from proki.core.actions import AskLlm
    from proki.core.signals import Variable
    llm = FakeLlm("Not now")
    await llm_channel.serve(Channels.bus, llm)
    assert await LLMQuestion("How long?", {"type": "object", "properties": {"minutes": {"type": "integer"}}}).invoke() == {"minutes": 30}
    assert await LLMQuestion("Say hi").invoke() == "Not now"
    assert await LLMQuestion("How many?", "integer").invoke() is None  # {"minutes": 30} isn't one
    answer = Variable("answer")
    await AskLlm("Start?", "answer").apply()
    assert answer.current() == "Not now" and llm.prompt == "Start?" and llm.schema is None  # a text: no schema


def test_a_jev_question_means_one_thing_whoever_asks_it():
    question = JevQuestion("A task", {"size":  {"type": "choice", "question": "How long?", "criteria": {"short": "under 25 min", "long": None}},
                                      "ready": {"type": "score",  "question": "How ready?", "criteria": {"5": "yes", "1": "no"}},
                                      "vague": {"type": "noul",   "question": "Too vague?"}})
    sent = question.resolve_input()["questions"]
    assert sent["size"] == {"type": "choice", "instructions": "How long?", "criteria": {"short": "under 25 min", "long": "long"}}  # no meaning: its label
    assert sent["ready"]["criteria"] == ["no", "yes"] and sent["vague"] == {"type": "noul", "instructions": "Too vague?"}
    got = lambda **said: question.resolve_output(said)
    assert got(size={"choice": "long", "probabilities": {"short": 0.2, "long": 0.8}, "confidence": 0.7})["size"] == {"index": 1, "conf": 0.7, "odds": [0.2, 0.8]}
    assert got(vague={"noul": 0.3})["vague"] == 0.3
    assert got(ready={"score": 0.75, "probabilities": {"0": 0.25, "1": 0.75}, "confidence": 0.5})["ready"] == {"score": 4.0, "conf": 0.5, "odds": [0.25, 0.75]}  # on its scale, 1 to 5
    with pytest.raises(ValueError, match="once"):
        JevQuestion("A task", {"ready": {"type": "score", "question": "How ready?", "criteria": {"1": "no", "1.0": "yes"}}})


async def test_the_same_question_is_answered_from_what_was_kept():
    class Counting:
        def __init__(self):
            self.asked = 0

        def ask(self, prompt, schema=None):
            self.asked += 1
            return None if prompt == "Fail" else f"{prompt}, {self.asked}"

    llm = Counting()
    await llm_channel.serve(Channels.bus, llm)
    hi = lambda type="string", fresh=False: LLMQuestion("Say hi", type, fresh=fresh).invoke()
    assert await hi() == await hi() == "Say hi, 1" and llm.asked == 1
    assert await hi("object") is None and llm.asked == 2  # another question, its schema too: asked
    assert await hi(fresh=True) == "Say hi, 3" == await hi()  # asked, and kept
    fail = lambda: LLMQuestion("Fail").invoke()
    assert await fail() is None and await fail() is None and llm.asked == 5  # none isn't kept


async def test_a_fields_ask_is_asked_once_and_again_only_as_it_changes():
    from proki.core.records.field import Asker

    class Saying:
        asked = 0

        def ask(self, prompt, schema=None):
            Saying.asked += 1
            return {"value": 3}

    class Kept(dict):
        times = 0

        def read(self, at):        return self.get(at)
        def keep(self, at, kept):  self[at], Kept.times = kept, Kept.times + 1
        def pop(self, at):         dict.pop(self, at, None)

    await llm_channel.serve(Channels.bus, Saying())
    cache, at = Kept(), (7, "hours", "llm")
    asks = Asker(cache)
    sent = {"channel": "llm", "about": "A task: the intro", "said": "How many hours?", "schema": {"type": "number"}}
    ask  = lambda said: asks.ask(at, lambda: said, None)
    ask(sent), ask(sent)  # out already: not asked twice
    await asks.drain()
    assert (cache[at]["of"], cache[at]["answer"], Saying.asked) == (sent, 3, 1)
    ask(sent)
    await asks.drain()
    assert Kept.times == 1  # what it'd ask is what it asked: not again
    ask({**sent, "about": "A task: the outro"})
    await asks.drain()
    assert Kept.times == 2 and Saying.asked == 2  # it changed: asked
    cache.pop(at)
    ask(sent)
    await asks.drain()
    assert Saying.asked == 3  # popped: asked for real, not answered from what the channel keeps



def test_jevs_own_answers_are_kept_as_its_questions_say():  # jev's replies, as it gives them
    lead = JevQuestion("A lead's email", {"buying_intent": {"type": "score", "question": "How ready is this lead to buy?", "criteria": {
        "0": "Just browsing, no stated need or timeline", "1": "Evaluating, comparing options without a deadline",
        "2": "Ready to buy, has budget and a clear need", "3": "Urgent, has a hard deadline and is asking to transact"}}})
    assert lead.resolve_input()["questions"]["buying_intent"]["criteria"] == [
        "Just browsing, no stated need or timeline", "Evaluating, comparing options without a deadline",
        "Ready to buy, has budget and a clear need", "Urgent, has a hard deadline and is asking to transact"]
    kept = lead.resolve_output({"buying_intent": {"type": "score", "score": 2.4915858608287347,
        "legend": {"0": "Just browsing, no stated need or timeline", "1": "Evaluating, comparing options without a deadline",
                   "2": "Ready to buy, has budget and a clear need", "3": "Urgent, has a hard deadline and is asking to transact"},
        "probabilities": {"0": 0.00950804431711839, "1": 0.05103997524235103, "2": 0.37781005573520804, "3": 0.5616419247053225},
        "confidence": 0.4915858608287347}})["buying_intent"]
    assert kept["score"] == pytest.approx(2.4915858608287347) and kept["conf"] == 0.4915858608287347  # its marks are its levels: jev's score
    assert kept["odds"] == [0.00950804431711839, 0.05103997524235103, 0.37781005573520804, 0.5616419247053225]
    team = JevQuestion("A message", {"team": {"type": "choice", "question": "Which team should handle this message?", "criteria": {
        "billing": "Payments, payouts, invoices, refunds", "technical": "Bugs, outages, integrations, API errors", "sales": "Pricing, upgrades, new accounts"}}})
    assert team.resolve_input()["questions"]["team"]["criteria"] == {
        "billing": "Payments, payouts, invoices, refunds", "technical": "Bugs, outages, integrations, API errors", "sales": "Pricing, upgrades, new accounts"}
    assert team.resolve_output({"team": {"type": "choice", "choice": "billing",
        "probabilities": {"billing": 0.9902778016558862, "technical": 0.009445052703279179, "sales": 0.000277145640834822},
        "confidence": 0.9854167024838293}})["team"] == {
        "index": 0, "conf": 0.9854167024838293, "odds": [0.9902778016558862, 0.009445052703279179, 0.000277145640834822]}


def test_a_jev_questions_criteria_are_taken_as_whoever_asks_has_them():
    kept = lambda kind, criteria: JevQuestion.check({"type": kind, "question": "?", "criteria": criteria})["criteria"]
    assert kept("choice", ["billing", "sales"]) == {"billing": None, "sales": None}  # labels alone
    assert kept("choice", [["billing", "payments"], ("sales", None)]) == {"billing": "payments", "sales": None}
    assert kept("choice", {"billing": "payments", "sales": None}) == {"billing": "payments", "sales": None}
    assert kept("score", ["browsing", "evaluating", "ready"]) == {"0": "browsing", "1": "evaluating", "2": "ready"}  # an even scale
    assert kept("score", {"5": "ready", "1": "browsing"}) == {"1": "browsing", "5": "ready"}  # its own, lowest first
    for kind, criteria, problem in [("choice", ["billing", "billing"], "duplicate option label"), ("choice", ["billing", 3], "invalid choice option"),
                                    ("choice", ["billing"], "two options or more"), ("score", ["ready", None], "says what it means"),
                                    ("score", {"low": "no", "high": "yes"}, "marks are numbers"), ("choice", "billing", "expected a mapping or a sequence")]:
        with pytest.raises(ValueError, match=problem):
            kept(kind, criteria)

async def test_nobody_answers_a_channel_without_a_worker():
    assert await JevQuestion("github.com", {"q": {"type": "noul", "question": "Work?"}}).invoke() == {} and await LLMQuestion("hi").invoke() is None


def test_a_program_in_code_is_named_with_an_at(tmp_path):
    from proki.programs.code.base import Ritual

    config = {"programs": [{"name": "plan", "initial": "s", "states": {"s": {}}}]}
    engine(tmp_path, config, programs=[lambda: Ritual("@plan")])
    assert {"plan", "@plan"} <= set(Program.registry)  # two programs: the names can't clash
    with pytest.raises(ValueError, match="program .plan.: a name is"):
        Ritual("plan")
    config = {"programs": [{"name": "@plan", "initial": "s", "states": {"s": {}}}]}
    with pytest.raises(ValueError, match="a name is letters"):
        engine(tmp_path, config)


async def test_the_programs_cycle_every_call_the_data_once_a_cycle_is_due(tmp_path):
    from proki.core.programs import Program

    e = engine(tmp_path, {"programs": [{"name": "p", "initial": "a", "states": {"a": {"next": "a"}}}]})
    await replay_cycle(e, at(0), rec=Record.of(at(0) - timedelta(minutes=1), at(0), {}))
    data = Stream.now
    await e.cycle(at(0) + timedelta(seconds=2))  # 2 s on: the programs', not the data's
    assert Stream.now == data and Program.now == at(0) + timedelta(seconds=2)
    Program.stop()
