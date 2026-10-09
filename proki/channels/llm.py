"""An LLM on the bus ("proki.ask.llm"): it picks an option, writes JSON for a schema, or
writes text (services/llm.py).

    await ask("Start a session?", ["Start", "Not now"])            1 (the option's index)
    await ask("How long?", schema={"type": "object", ...})         {"minutes": 30}
    await ask("Say hi")                                            "Hi!"

    await serve(bus, llm)   the worker: answers with `llm`, one call at a time

Options can carry what they mean: [("deep", "coding, writing"), "shallow"].
"""

from __future__ import annotations

import asyncio
from typing import Any

from proki.channels.base import Options, chosen, labelled, request
from proki.services.llm import Llm
from proki.services.nats import Bus


async def ask(context: str, options: Options | None = None, schema: dict | None = None, timeout: float = 10) -> Any:
    """The LLM's answer: an option's index, the JSON for `schema`, or its text (None: no answer)."""
    options = None if options is None else labelled(options)
    answer = await request("llm", {"context": context, "options": options, "schema": schema}, timeout)

    if options is not None:  return chosen(answer, options)
    if schema is not None:   return answer
    return answer if isinstance(answer, str) and answer.strip() else None


async def serve(bus: Bus, llm: Llm) -> None:
    """Answer "proki.ask.llm" with `llm`, on a thread (its HTTP call blocks)."""
    async def handle(request: dict) -> dict:
        context, options, schema = request["context"], request.get("options"), request.get("schema")
        try:
            if options:                 answer = await asyncio.to_thread(choice, llm, context, options)
            elif schema is not None:    answer = await asyncio.to_thread(llm.ask, context, schema=schema)
            else:                       answer = await asyncio.to_thread(llm.ask, context)
        except Exception:  # a failed call is no answer
            answer = None
        return {"answer": answer}

    await bus.subscribe("proki.ask.llm", handle, workers=1)


def choice(llm: Llm, context: str, options: list[list]) -> int | None:
    """The index of the option the LLM picks. Its answer must be one of the labels (a JSON
    schema's enum), so it can't wander off ("shallow: email, chat, admin"). Raises LlmError
    if it doesn't answer."""
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
