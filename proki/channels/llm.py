"""An LLM on the bus ("proki.ask.llm"): it writes JSON for a schema, or text.

    await ask("How long?", schema={"type": "object", ...})         {"minutes": 30}
    await ask("Say hi")                                            "Hi!"

    await serve(bus, llm)   the worker: answers with `llm`, one call at a time
"""

from __future__ import annotations

import asyncio
from typing import Any

from proki.channels.base import request
from proki.services.llm import Llm
from proki.services.nats import Bus


async def ask(context: str, schema: dict | None = None, timeout: float = 10) -> Any:
    """The LLM's answer: the JSON for `schema`, else its text (None: no answer)."""
    answer = await request("llm", {"context": context, "schema": schema}, timeout)
    if schema is not None:  return answer
    return answer if isinstance(answer, str) and answer.strip() else None


async def serve(bus: Bus, llm: Llm) -> None:
    """Answer "proki.ask.llm" with `llm`, on a thread (its HTTP call blocks)."""
    async def handle(request: dict) -> dict:
        context, schema = request["context"], request.get("schema")
        try:
            answer = await asyncio.to_thread(llm.ask, context) if schema is None else await asyncio.to_thread(llm.ask, context, schema=schema)
        except Exception:  # a failed call is no answer
            answer = None
        return {"answer": answer}

    await bus.subscribe("proki.ask.llm", handle, workers=1)
