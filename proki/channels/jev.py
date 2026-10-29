"""jev on the bus ("proki.ask.jev"): named questions about a short text, each answered with
how likely each answer is.

    await JevQuestion('A task: "write the intro"', {
        "size":  {"type": "choice", "question": "How long?", "criteria": {"short": "under 25 min", "long": "over 2 h"}},
        "vague": {"type": "noul",   "question": "Too vague to start?"},
        "ready": {"type": "score",  "question": "How ready is it to start?",
                  "criteria": {"1": "not at all: it needs planning first", "5": "ready: the first step is clear"}},
    }).invoke()
    →  {"size":  {"index": 0, "conf": 0.78, "odds": [0.8, 0.2]},
        "vague": 0.1,
        "ready": {"score": 4.0, "conf": 0.75, "odds": [0.25, 0.75]}}

    await serve(bus, jev)   the worker: answers with `jev`

A question is its type, what it asks, and its criteria:

    noul      yes or no: no criteria
    choice    its options, in order: {label: what it means}, a list of labels, or a list of
              [label, what it means]
    score     its scale: {mark: what it means}, the marks any numbers ("1", "5"), or a list
              of what each level means, lowest first (marks 0, 1, 2, ...)

Its answer:

    noul      the probability of yes
    choice    index   the option picked, by its place
              conf    how sure jev is of it
              odds    each option's probability, in order
    score     score   where it is on its scale (0.25 at 1, 0.75 at 5: 4)
              conf    how sure jev is of it
              odds    each mark's probability, lowest first

A question jev doesn't answer has none ({}: no answer at all).
"""

from __future__ import annotations

from typing import Any

from proki.channels import base
from proki.services.jev import Jev
from proki.services.nats import Bus
from proki.utils import numeric


class JevQuestion(base.Question):
    """Named questions, one or more, answered by name (above)."""

    CHANNEL = "jev"
    ODDS    = {"type": "array", "items": {"type": "number"}}
    ANSWERS = {   # each kind of question, its answer's type
        "noul":   {"type": "number"},
        "choice": {"type": "object", "properties": {"index": {"type": "integer"}, "conf": {"type": "number"}, "odds": ODDS}},
        "score":  {"type": "object", "properties": {"score": {"type": "number"},  "conf": {"type": "number"}, "odds": ODDS}},
    }

    def __init__(self, context: str, questions: dict[str, dict], timeout: float = 10, fresh: bool = False):
        super().__init__(context, timeout, fresh)
        if not isinstance(questions, dict) or not questions:        raise ValueError(f"jev's questions need to be a non-empty dict ({questions!r})")
        if not all(isinstance(n, str) and n for n in questions):    raise ValueError(f"jev's questions' names need to be string ({questions!r})")

        self.questions = {name: JevQuestion.check(q) for name, q in questions.items()}

    @staticmethod
    def check(q: Any) -> dict:
        """A question as it's asked. ValueError unless it's one jev takes: a noul with no criteria;
        a choice with two options or more, none twice; a score with two marks or more, each a
        number once, each saying what it means."""
        if not isinstance(q, dict) or set(q) - {"type", "question", "criteria"}:
            raise ValueError(f"a question to jev is {{type, question, criteria}} ({q!r})")

        kind, said, criteria = q.get("type"), q.get("question"), q.get("criteria")
        if kind not in JevQuestion.ANSWERS:                 raise ValueError(f"a question to jev is a noul, a choice or a score ({kind!r})")
        if not isinstance(said, str) or not said.strip():   raise ValueError(f"a question to jev asks something: a text ({said!r})")
        if kind == "noul" and criteria:                     raise ValueError("a noul (yes or no) has no criteria")
        if kind == "noul":      return {"type": kind, "question": said, "criteria": {}}
        if kind == "choice":    criteria = JevQuestion.normalize_choices(criteria)
        if kind == "score":     criteria = JevQuestion.normalize_scales(criteria)
        if len(criteria) < 2:   raise ValueError(f"a {kind} question has two {'options' if kind == 'choice' else 'scales'} or more ({criteria!r})")
        return {"type": kind, "question": said, "criteria": criteria}

    @staticmethod
    def normalize_choices(given: Any) -> dict[str, str | None]:
        """A choice's options, {label: what it means}, from any of their forms."""
        if isinstance(given, dict):             items = given.items()
        elif isinstance(given, list | tuple):   items = given
        else:                                   raise ValueError(f"expected a mapping or a sequence of labels/options, got {given!r}")

        options: dict[str, str | None] = {}

        for item in items:
            if isinstance(item, str):
                label, meaning = item, None
            elif isinstance(item, list | tuple) and len(item) == 2:
                label, meaning = item
            else:
                raise ValueError(f"invalid choice option: {item!r}")

            if not isinstance(label, str) or not label:
                raise ValueError(f"option label must be a non-empty string: {item!r}")
            if meaning is not None and not isinstance(meaning, str):
                raise ValueError(f"option meaning must be a string or None: {item!r}")
            if label in options:
                raise ValueError(f"duplicate option label: {label!r}")

            options[label] = meaning

        return options

    @staticmethod
    def normalize_scales(given: Any) -> dict[str, str]:
        """A score's marks, {mark: what it means}, lowest first, from either of their forms."""
        if isinstance(given, list | tuple):
            given = dict(enumerate(given))

        if not isinstance(given, dict):
            raise ValueError(f"a score's scale is {{mark: what it means}}, or a list of what each level means ({given!r})")
        if not all(isinstance(means, str) and means.strip() for means in given.values()):
            raise ValueError(f"a score's mark says what it means: jev reads only that ({given!r})")

        try:
            marks = {float(key) for key in given}
        except (TypeError, ValueError):
            raise ValueError(f"a score's marks are numbers ({list(given)})") from None
        if len(marks) < len(given):
            raise ValueError(f"a score's mark is on its scale once ({list(given)})")
        return {str(key): given[key] for key in sorted(given, key=float)}

    def resolve_input(self) -> dict:
        questions = {}
        for name, q in self.questions.items():
            questions[name] = {"type": q["type"], "instructions": q["question"]}
            if q["type"] == "choice":   questions[name]["criteria"] = {key: means or key for key, means in q["criteria"].items()}
            if q["type"] == "score":    questions[name]["criteria"] = list(q["criteria"].values())
        return {"context": self.context, "questions": questions}

    def resolve_output(self, answer: Any) -> dict[str, dict | None]:
        if not isinstance(answer, dict):
            return {}

        answers = {}
        for name, q in self.questions.items():
            kind, said, keys = q["type"], answer.get(name), list(q["criteria"])
            if not isinstance(said, dict):
                continue
            if kind == "noul":
                answers[name] = said["noul"] if numeric(said.get("noul")) else None
                continue

            given = said.get("probabilities") or {}
            odds  = [p if numeric(p := given.get(key if kind == "choice" else str(i))) else 0.0 for i, key in enumerate(keys)]
            conf  = said["confidence"] if numeric(said.get("confidence")) else None
            answers[name] = {"conf": conf, "odds": odds}

            if kind == "choice":
                named = keys.index(said["choice"]) if said.get("choice") in keys else None
                index = odds.index(max(odds)) if any(odds) else named
                answers[name]["index"] = index
            elif total := sum(odds):
                answers[name]["score"] = sum(float(key) * p for key, p in zip(keys, odds)) / total
        
        return answers


async def serve(bus: Bus, jev: Jev) -> None:
    """Answer "proki.ask.jev" with `jev`."""
    await base.serve(bus, "jev", lambda request: jev.ask(request["context"], request["questions"]))
