"""jev on the bus ("proki.ask.jev"): named questions about a short text, answered with
their probabilities (services/jev.py).

    await ask('A task: "write the intro"', {
        "size":  {"type": "choice", "instructions": "How long?", "criteria": {"short": "...", "long": "..."}},
        "vague": {"type": "noul", "instructions": "Too vague to start?"},
    })
    →  {"size": {"choice": "short", "probabilities": {"short": 0.8, "long": 0.2}}, "vague": {"noul": 0.1}}

    await pick("github.com", [("deep", "coding, writing"), "shallow"])    1 (the option's index)

    await serve(bus, jev)   the worker: answers with `jev`, one call at a time

Options can carry what they mean, as for the LLM (llm.py): [("deep", "coding, writing"), "shallow"].
"""

from __future__ import annotations

import asyncio

from proki.channels.base import Options, paired, request
from proki.services.jev import Jev
from proki.services.nats import Bus


async def ask(context: str, questions: dict, timeout: float = 10) -> dict | None:
    """jev's answers to `questions`, by name (None: no answer)."""
    answers = await request("jev", {"context": context, "questions": questions}, timeout)
    return answers if isinstance(answers, dict) else None


async def pick(context: str, options: Options, timeout: float = 10) -> int | None:
    """The index of the option jev picks (None: no answer). jev gets one choice question,
    where each option is described by its criteria (or its label when it has none)."""
    options = paired(options)
    keys = [f"o{i}" for i in range(len(options))]  # options can be any text, so jev gets plain keys
    question = {
        "type": "choice",
        "instructions": "Which option fits best?",
        "criteria": {key: criteria or label for key, (label, criteria) in zip(keys, options)},
    }
    answers = await ask(context, {"pick": question}, timeout)

    answer = answers.get("pick") if answers else None
    key = answer.get("choice") if isinstance(answer, dict) else None
    return keys.index(key) if key in keys else None


async def serve(bus: Bus, jev: Jev) -> None:
    """Answer "proki.ask.jev" with `jev`, on a thread (its HTTP call blocks)."""
    async def handle(request: dict) -> dict:
        try:
            answers = await asyncio.to_thread(jev.ask, request["context"], request["questions"])
        except Exception:  # a failed call is no answer
            answers = None
        return {"answer": answers}

    await bus.subscribe("proki.ask.jev", handle, workers=1)
