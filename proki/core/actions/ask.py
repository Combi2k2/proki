"""Questions, by who answers, each answer into a variable of the state:

    ask_usr   you: an option you pick, or what you type
    ask_jev   jev: several at once, each a yes or no, a choice or a score
    ask_llm   an LLM: an answer of the variable's type
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any, TypedDict

from proki.channels.base import Option, paired
from proki.channels.jev import JevQuestion
from proki.channels.llm import LLMQuestion
from proki.channels.popup import Popup
from proki.core.actions.base import Action, Context, LValue, RValue
from proki.core.signals import Variable
from proki.errors import ActionError
from proki.types import accept, typename


class AskUsr(Action):
    """A question to you, the answer into a variable of the state.

        {"ask_usr": {"context": "Start a session?", "title": "Ready?", "options": ["Start", "Not now"], "result": "answer", "default": 1}}

        context       what's said
        options       what can be picked: texts, or an expression giving them ("track.labels");
                      none to pick, it isn't asked. Left out, you type the answer
        result        the variable for the answer: the option's index, or what you typed
        default       the option picked already, by its index, or an expression giving it or its text
        title         its heading
        immediate     no "Later": it's to be answered now
        timeout       how many seconds it waits (120)

    An option called "OK" or "Later" is that button. No answer, or until it comes, the result is unknown: it
    was put off, nobody was there, the time ran out, or there was nothing to pick (then it isn't asked).
    """

    ABOUT   = ("a question to you, its answer into a variable of the state (result): the option's index, or what "
               "you type (no options), under its title. The option picked already (default). It gets an id as it's "
               "added: its pictures and sounds are its picks (set_picks), drawn along with the questions' pool")
    EXAMPLE = {"ask_usr": {"context": "Start a session?", "title": "Ready?", "options": ["Start", "Not now"], "result": "answer", "default": 1}}

    def __init__(self, context: Context, result: LValue, title: str, options: list[str] | RValue | None = None,
                    default: RValue | int | None = None, timeout: float = 120, immediate: bool = False):
        if not isinstance(title, str) or not title:     raise ActionError(f"ask_usr: title is a text ({title!r})")
        if not isinstance(immediate, bool):             raise ActionError(f"ask_usr: immediate is true or false ({immediate!r})")

        self.timeout   = timeout
        self.context   = Context(context, "ask_usr")
        self.options   = self.resolve(options, default)
        self.default   = None if default is None else RValue(default)
        self.title     = title
        self.immediate = immediate
        self.answers   = "string" if self.options is None else "integer"
        self.result    = LValue(result)  # answer := ask(...): what it reads first
        self.result.take(self.answers)

    @staticmethod
    def resolve(options: Any, default: Any = None) -> list[Option] | str | None:
        """Its options as written: a list of texts, or an expression; `default`, an option's index, or an expression giving it or its text."""
        if options is None and default is not None:      raise ActionError("ask_usr: default is an option, so it needs options")
        if type(default) not in (int, str, type(None)):  raise ActionError(f"ask_usr: default is an option's index, or an expression ({default!r})")  # not true or false
        if options is None:
            return None
        if isinstance(options, str):
            return RValue(options)
        if not isinstance(options, list) or not options:                       raise ActionError("ask_usr: options is a list of texts, or an expression")
        if bad := [o for o in options if not isinstance(o, str) or not o]:     raise ActionError(f"ask_usr: an option is a text ({bad[0]!r})")
        if len(set(options)) != len(options):                                  raise ActionError(f"ask_usr: an option is listed twice ({options})")
        if type(default) is int and not 0 <= default < len(options):           raise ActionError(f"ask_usr: default is an option's index, 0 to {len(options) - 1} ({default!r})")
        return [(o, None) for o in options]

    @staticmethod
    def compute(entries: list | str | None) -> list[Option] | None:
        """Its options now, each (label, what it means): an expression's value gives texts, or
        [label, what it means] each. ValueError for anything else."""
        value = entries.value() if isinstance(entries, RValue) else entries
        if not isinstance(value, list | tuple):
            return None if entries is None else []
        return paired([o for o in value if o is not None])

    async def apply(self) -> None:
        self.result.set(None)  # unknown until it's answered
        choices = self.compute(self.options)
        labels  = None if choices is None else [label for label, _ in choices]
        if labels == []:  # nothing to pick: not asked
            return
        picked = None if self.default is None else self.default.value()
        picked = labels.index(picked) if labels and picked in labels else picked if type(picked) is int and picked >= 0 else None
        answer = await Popup.ask(self.context.said(), labels, self.timeout, title=self.title, id=self.id, immediate=self.immediate or None, selected=picked)
        self.result.set(answer)

    def read(self) -> list[RValue]:
        given = [e for e in (self.options, self.default) if isinstance(e, RValue)]
        return [*self.context.values.values(), *given, *self.result.read()]

    def write(self) -> list[Variable]:
        return [self.result.variable]

    def typecheck(self) -> None:
        if not accept(into := self.result.type, self.answers):
            raise ActionError(f"ask_usr: {self.result} is of type {typename(into)}: the answer is {typename(self.answers)}")
        if self.default is not None and not (accept("integer", given := self.default.type) or accept("string", given)):
            raise ActionError(f"ask_usr: default is an option's index or its text, {self.default} gives {typename(given)}")

    def __repr__(self) -> str:
        shown = "text" if self.options is None else self.options if isinstance(self.options, RValue) else [o for o, _ in self.options]
        return f"ask_usr {self.context!r} {shown} → {self.result}"


class Question(TypedDict, total=False):
    """A question to jev, as written (see AskJev)."""

    type     : str
    question : str
    criteria : dict | list | RValue
    result   : LValue


class AskJev(Action):
    """Questions to jev about what's said, asked at once, each answer into a variable of the state.

        {"ask_jev": {
            "context":   {"format": "A note someone wrote: {text}", "values": {"text": "todo.content"}},
            "questions": [{"type": "choice", "question": "What is it?", "result": "kind",
                           "criteria": {"Todo": "something to do", "Idea": None}},
                          {"type": "noul",   "question": "Is it urgent?", "result": "urgent"},
                          {"type": "score",  "question": "How big is it?", "result": "size",
                           "criteria": {"1": "a few minutes", "10": "a week or more"}}]
        }}

        context     what's said
        questions   each {type, question, criteria, result}: what it asks, and the variable for its answer
        timeout     how many seconds it waits (10)

    A question's type says what it answers:

        noul      yes or no                  the chance of yes, 0 to 1
        choice    one of its criteria        .index, .conf (how likely), .odds (each option's)
        score     where it is on a scale     .score (7.3: most of the way from 1 to 10), .conf, .odds

    A noul has no criteria; a choice's are {label: what it means} or a list of labels; a score's,
    {mark: what it means} or what each level means, lowest first. Either can be an expression
    giving them ("track.labels"): if what it gives can't be asked, that question isn't. No answer,
    or until it comes, a result is unknown.
    """

    ABOUT   = ("questions to jev about its context, asked at once, each into a result of its own: a noul (yes or no) "
               "answers the chance of yes; a choice (one of its criteria, {label: meaning} or a list of labels) its "
               ".index, .conf and .odds; a score (where it is on a scale of its criteria, {\"1\": meaning, \"5\": ...} "
               "or what each level means, lowest first) its .score, .conf and .odds")
    EXAMPLE = {"ask_jev": {"context":   {"format": "A note someone wrote: {text}", "values": {"text": "todo.content"}},
                           "questions": [{"type": "choice", "question": "What is it?",   "result": "kind", "criteria": {"Todo": "something to do", "Idea": None}},
                                         {"type": "noul",   "question": "Is it urgent?", "result": "urgent"}]}}

    def __init__(self, context: Context, questions: list[Question], timeout: float = 10):
        if not isinstance(questions, list) or not questions:
            raise ActionError("ask_jev: questions is a list, each {type, question, criteria, result}")

        self.timeout   = timeout
        self.context   = Context(context, "ask_jev")
        self.questions = [self.resolve(q) for q in questions]
        if len(results := [str(q["result"]) for q in self.questions]) != len(set(results)):
            raise ActionError(f"ask_jev: each question answers into a variable of its own ({', '.join(results)})")

    @staticmethod
    def resolve(entry: Any) -> dict:
        """A question as written (see above), its result the variable. ActionError for one jev
        can't be asked (criteria from an expression: as they're asked)."""
        MESSAGE = "a question takes {type, question, criteria, result}"
        KEYS_REQUIRED = {"type", "question", "result"}
        KEYS_OPTIONAL = {"type", "question", "result", "criteria"}
        if not isinstance(entry, dict):             raise ActionError(f"ask_jev: {MESSAGE} ({entry!r})")
        if unknown := set(entry) - KEYS_OPTIONAL:   raise ActionError(f"ask_jev: {MESSAGE}: unknown {', '.join(sorted(unknown))}")
        if missing := KEYS_REQUIRED - set(entry):   raise ActionError(f"ask_jev: {MESSAGE}: missing {', '.join(sorted(missing))}")
        if (answers := JevQuestion.ANSWERS.get(entry["type"])) is None:
            raise ActionError(f"ask_jev: a question to jev is a noul, a choice or a score ({entry['type']!r})")

        q = {k: entry[k] for k in ("type", "question", "criteria") if k in entry}
        if isinstance(q.get("criteria"), str):
            q["criteria"] = RValue(q["criteria"])
        else:
            try:
                q = JevQuestion.check(q)
            except ValueError as e:
                raise ActionError(f"ask_jev: {e}") from None
        (result := LValue(entry["result"])).take(answers)
        return q | {"result": result, "answers": answers}

    async def apply(self) -> None:
        def validate(q: dict) -> dict | None:
            q["result"].set(None)
            criteria = q["criteria"].value() if isinstance(q.get("criteria"), RValue) else q.get("criteria")
            with suppress(ValueError):
                return JevQuestion.check({"type": q["type"], "question": q["question"], "criteria": criteria})
        
        req = {f"q{i}": payload for i, q in enumerate(self.questions) if (payload := validate(q))}
        res = await JevQuestion(self.context.said(), req, self.timeout).invoke() if req else {}

        for i, q in enumerate(self.questions):
            q["result"].set(res.get(f"q{i}"))

    def read(self) -> list[RValue]:
        criteria = [q["criteria"] for q in self.questions if isinstance(q.get("criteria"), RValue)]
        return [*self.context.values.values(), *criteria, *(at for q in self.questions for at in q["result"].read())]

    def write(self) -> list[Variable]:
        return [q["result"].variable for q in self.questions]

    def typecheck(self) -> None:
        for q in self.questions:
            if not accept(into := q["result"].type, q["answers"]):
                raise ActionError(f"ask_jev: {q['result']} is of type {typename(into)}: the answer is {typename(q['answers'])}")

    def __repr__(self) -> str:
        return f"ask_jev {self.context!r} " + ", ".join(f"{q['type']} {q['question']!r} → {q['result']}" for q in self.questions)


class AskLlm(Action):
    """A question to an LLM, the answer into a variable, in its type.

        {"ask_llm": {"context": "How many people does this need?", "result": "need"}}

        context   what's said
        result    the variable for the answer: in its type (a text if it has none), an object's
                  fields read with a dot (need.people)
        timeout   how many seconds it waits (10)

    No answer, or until it comes, the result is unknown.
    """

    ABOUT   = ("a question to the LLM: it answers in the type of the variable it goes into (a text if it has none), "
               "an object's fields read with a dot: need.people")
    EXAMPLE = {"ask_llm": {"context": "How many people does this need?", "result": "need"}}

    def __init__(self, context: Context, result: LValue, timeout: float = 10):
        self.timeout = timeout
        self.context = Context(context, "ask_llm")
        self.result  = LValue(result)
        self.answers = "string" if self.result.steps else self.typed()  # a place's: once all's made
        self.result.take(self.answers)

    def typed(self) -> str | dict:
        """What it answers: its result's type, a text if it has none."""
        typed = self.result.type if self.result.steps else self.result.variable._typed
        return typed if typed not in (None, "any", {}) else "string"

    async def apply(self) -> None:
        self.result.set(None)  # unknown until it's answered
        self.result.set(await LLMQuestion(self.context.said(), self.answers, self.timeout).invoke())

    def read(self) -> list[RValue]:
        return [*self.context.values.values(), *self.result.read()]

    def write(self) -> list[Variable]:
        return [self.result.variable]

    def typecheck(self) -> None:
        if self.result.steps:
            self.answers = self.typed()
        if not accept(into := self.result.type, self.answers):
            raise ActionError(f"ask_llm: {self.result} is of type {typename(into)}: the answer is {typename(self.answers)}")

    def __repr__(self) -> str:
        return f"ask_llm {self.context!r} → {self.result}"
