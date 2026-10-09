"""jev on the bus ("proki.ask.jev"): named questions about a short text, answered with
their probabilities (services/jev.py).

    await ask('A task: "write the intro"', {
        "size":  {"type": "choice", "instructions": "How long?", "criteria": {"short": "...", "long": "..."}},
        "vague": {"type": "noul", "instructions": "Too vague to start?"},
    })
    →  {"size": {"choice": "short", "probabilities": {"short": 0.8, "long": 0.2}}, "vague": {"noul": 0.1}}

    await serve(bus, jev)   the worker: answers with `jev`, one call at a time
"""

from __future__ import annotations

import asyncio

from proki.channels.base import request
from proki.services.jev import Jev
from proki.services.nats import Bus


async def ask(context: str, questions: dict, timeout: float = 10) -> dict | None:
    """jev's answers to `questions`, by name (None: no answer)."""
    answers = await request("jev", {"context": context, "questions": questions}, timeout)
    return answers if isinstance(answers, dict) else None


async def serve(bus: Bus, jev: Jev) -> None:
    """Answer "proki.ask.jev" with `jev`, on a thread (its HTTP call blocks)."""
    async def handle(request: dict) -> dict:
        try:
            answers = await asyncio.to_thread(jev.ask, request["context"], request["questions"])
        except Exception:  # a failed call is no answer
            answers = None
        return {"answer": answers}

    await bus.subscribe("proki.ask.jev", handle, workers=1)
