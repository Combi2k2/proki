"""An LLM on the bus ("proki.ask.llm"): it picks an option, writes JSON for a schema, or
writes text (services/llm.py).

    await pick("Start a session?", ["Start", "Not now"])           1 (the option's index)
    await ask("How long?", schema={"type": "object", ...})         {"minutes": 30}
    await ask("Say hi")                                            "Hi!"
    await ask("Start a session?", ["Start", "Not now"])            1: with options, `ask` picks

    await serve(bus, llm)   the worker: answers with `llm`, one call at a time

Options can carry what they mean, as for jev (jev.py): [("deep", "coding, writing"), "shallow"].
"""

from __future__ import annotations

import asyncio
from typing import Any

from proki.channels.base import Options, paired, picked, request
from proki.services.llm import Llm
from proki.services.nats import Bus


async def ask(context: str, options: Options | None = None, schema: dict | None = None, timeout: float = 10) -> Any:
    """The LLM's answer: an option's index (`pick`), the JSON for `schema`, or its text
    (None: no answer)."""
    if options is not None:  return await pick(context, options, timeout)

    answer = await request("llm", {"context": context, "options": None, "schema": schema}, timeout)
    if schema is not None:   return answer
    return answer if isinstance(answer, str) and answer.strip() else None


async def pick(context: str, options: Options, timeout: float = 10) -> int | None:
    """The index of the option the LLM picks (None: no answer). The worker makes it answer
    with one of the labels (`picking`)."""
    options = paired(options)
    answer = await request("llm", {"context": context, "options": options, "schema": None}, timeout)
    return picked(answer, options)


async def serve(bus: Bus, llm: Llm) -> None:
    """Answer "proki.ask.llm" with `llm`, on a thread (its HTTP call blocks)."""
    async def handle(request: dict) -> dict:
        context, options, schema = request["context"], request.get("options"), request.get("schema")
        try:
            if options:                 answer = await asyncio.to_thread(picking, llm, context, options)
            elif schema is not None:    answer = await asyncio.to_thread(llm.ask, context, schema=schema)
            else:                       answer = await asyncio.to_thread(llm.ask, context)
        except Exception:  # a failed call is no answer
            answer = None
        return {"answer": answer}

    await bus.subscribe("proki.ask.llm", handle, workers=1)


def picking(llm: Llm, context: str, options: list[list]) -> int | None:
    """The worker's side of `pick`: the index of the option the LLM picks. Its answer must
    be one of the labels (a JSON schema's enum), so it can't wander off ("shallow: email,
    chat, admin"). Raises LlmError if it doesn't answer."""
    labels = [label for label, _ in options]
    listing = "\n".join(f"- {label}" + (f": {criteria}" if criteria else "") for label, criteria in options)
    schema = {
        "type": "object",
        "properties": {"option": {"type": "string", "enum": labels}},
        "required": ["option"],
    }

    answer = llm.ask(f"{context}\n\nOptions:\n{listing}\n\nPick one of the options.", schema=schema)
    option = answer.get("option") if isinstance(answer, dict) else None
    return labels.index(option) if option in labels else None
