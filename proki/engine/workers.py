"""Who answers jev's and the LLM's queues (core/ask.py): a worker each, subscribed on the
bus, calling the service. One call at a time each, so a service is never flooded.

    serve_jev(bus, jev)   "proki.ask.jev": jev picks one of the options, by their criteria
    serve_llm(bus, llm)   "proki.ask.llm": an option's index, the JSON for a schema, or text

The UI answers "proki.ask.usr" itself. A failed call answers None (no answer).
"""

from __future__ import annotations

from collections.abc import Callable

from proki.services.jev import Jev
from proki.services.llm import Llm
from proki.services.nats import Bus


def serve_jev(bus: Bus, jev: Jev) -> None:
    def handle(request: dict, reply: Callable[[dict], None]) -> None:
        reply({"answer": jev_choice(jev, request["context"], request.get("options") or [])})

    bus.subscribe("proki.ask.jev", handle, workers=1)


def serve_llm(bus: Bus, llm: Llm) -> None:
    def handle(request: dict, reply: Callable[[dict], None]) -> None:
        context, options, schema = request["context"], request.get("options"), request.get("schema")
        try:
            if options:
                answer = llm_choice(llm, context, options)
            elif schema is not None:
                answer = llm.ask(context, schema=schema)
            else:
                answer = llm.complete(context)
        except Exception:  # a failed call is no answer
            answer = None
        reply({"answer": answer})

    bus.subscribe("proki.ask.llm", handle, workers=1)


def jev_choice(jev: Jev, context: str, options: list[list]) -> int | None:
    """jev's choice: the chosen option's index (None if the call fails)."""
    if not options:
        return None
    keys = {f"o{i}": i for i in range(len(options))}  # options can be any text
    try:
        answer = jev.ask(context, {"answer": {
            "type": "choice", "instructions": "Which option fits best?",
            "criteria": {key: options[i][1] or options[i][0] for key, i in keys.items()},
        }})["answer"]
        return keys.get(answer["choice"])
    except Exception:
        return None


def llm_choice(llm: Llm, context: str, options: list[list]) -> int | None:
    """The index of the option an LLM names (None if it fails or names none)."""
    labels = [label for label, _ in options]
    listing = "\n".join(f"- {label}" + (f": {criteria}" if criteria else "") for label, criteria in options)
    reply = llm.complete(f"{context}\n\nOptions:\n{listing}\n\nReply with exactly one of the options, as written, "
                         "and nothing else.")
    return pick(reply, labels)


def pick(reply: str | None, labels: list[str]) -> int | None:
    """The index of the option a reply names (case and quotes aside), or None."""
    if not reply:
        return None
    said = reply.strip().strip('"“”\'`.*- ').casefold()
    return next((i for i, label in enumerate(labels) if label.casefold() == said), None)
