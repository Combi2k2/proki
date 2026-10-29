"""An LLM on the bus ("proki.ask.llm"): a question, answered in a type.

    await LLMQuestion("Say hi").invoke()                                    →  "Hi!"
    await LLMQuestion("How many people?", "integer").invoke()               →  3
    await LLMQuestion("How long?", {"type": "object", ...}).invoke()        →  {"minutes": 30}

    await serve(bus, llm)   the worker: answers with `llm`

The type is a name ("string", the default, "integer", ...) or a JSON schema. An answer not of it is none.
"""

from __future__ import annotations

from typing import Any

from proki.channels import base
from proki.channels.base import text
from proki.services.llm import Llm
from proki.services.nats import Bus
from proki.types import Type, oftype, schema


class LLMQuestion(base.Question):
    """A question, answered in its type (above). A type there isn't is a ValueError."""

    CHANNEL = "llm"

    def __init__(self, context: str, type: Type = "string", timeout: float = 10, fresh: bool = False):
        super().__init__(context, timeout, fresh)
        self.type = made = schema(type)
        if made in ({}, {"type": "string"}):    self.schema = None
        elif made.get("type") == "object":      self.schema = {"required": list(made.get("properties", {})), **made}
        else:                                   self.schema = {"type": "object", "properties": {"value": made}, "required": ["value"]}

    def resolve_input(self) -> dict:
        return {"context": self.context, "schema": self.schema}

    def resolve_output(self, answer: Any) -> Any:
        if self.schema is None:
            return text(answer)
        if self.type.get("type") != "object":
            answer = answer.get("value") if isinstance(answer, dict) else None
        return answer if oftype(answer, self.type) else None


async def serve(bus: Bus, llm: Llm) -> None:
    """Answer "proki.ask.llm" with `llm`."""
    await base.serve(bus, "llm", lambda request: llm.ask(request["context"], schema=request.get("schema")))
