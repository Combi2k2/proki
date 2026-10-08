"""Asking: you, jev or an LLM, through the message bus (services/nats.py), one queue each.

    ask_usr(context, options=None, timeout=120)                  you, through the UI
    ask_jev(context, options, timeout=10)                        jev picks an option
    ask_llm(context, options=None, schema=None, timeout=10)      an LLM

Every request has the same shape:

    context   the question, as it's shown or sent (already filled in: no placeholders left)
    options   ["Start", "Not now"], or [("Start", "focus is building"), ...] with what each
              option means (its criteria, for jev and an LLM), or None
    schema    a JSON schema for the LLM's answer (LLM only)

What comes back:

    with options      the chosen option's index (0, 1, ...)
    no options        the text (typed by you, or written by the LLM)
    with a schema     the parsed JSON (LLM only)
    no answer         None (nobody answered, dismissed, or past `timeout` seconds)

Each function waits for the answer. A caller that mustn't wait (a program's turn) uses
`ask_later(then, channel, ...)`: the request goes out at once, and `then(answer)` runs at
the engine's next turn after the answer comes (core/later.py), like the `ask` action does. A question to you
that times out is taken off the screen.

The subjects: "proki.ask.usr", "proki.ask.jev", "proki.ask.llm", answered by the UI and by
the workers in engine/workers.py. One-way messages to the UI go to "proki.ui" (core/ui.py).
"""

from __future__ import annotations

import itertools
import threading
from collections import Counter
from collections.abc import Callable, Sequence
from typing import Any, ClassVar

from proki.core.later import Later
from proki.services.nats import Bus, LocalBus

Options = Sequence[str | tuple[str, str | None]] | None
UI = "proki.ui"


class Asking:
    """The bus questions go through (the app sets it), and how many wait for an answer."""

    bus: ClassVar[Bus] = LocalBus()
    out: ClassVar[Counter] = Counter()  # questions waiting, by channel
    _ids: ClassVar[itertools.count] = itertools.count(1)
    _lock: ClassVar[threading.Lock] = threading.Lock()


def ask_usr(context: str, options: Options = None, timeout: float = 120, **show: Any) -> int | str | None:
    """Ask you. `show`: how the UI shows it (urgent=True, alarm="session", placeholder="...",
    skip="That's all", text="what's typed already")."""
    return ask("usr", context, options, None, timeout, show)


def ask_jev(context: str, options: Options, timeout: float = 10) -> int | None:
    """Let jev pick one of `options`."""
    return ask("jev", context, options, None, timeout)


def ask_llm(context: str, options: Options = None, schema: dict | None = None, timeout: float = 10) -> Any:
    """Ask an LLM: an option's index, its JSON (`schema`), or its text."""
    return ask("llm", context, options, schema, timeout)


def ask(channel: str, context: str, options: Options = None, schema: dict | None = None, timeout: float = 10,
        show: dict | None = None) -> Any:
    """Send the request to `channel`'s queue and wait for its answer (see above)."""
    subject, request, answer = _request(channel, context, options, schema, show)
    return answer(Asking.bus.request(subject, request, timeout))


def ask_later(then: Callable[[Any], None], channel: str, context: str, options: Options = None,
              schema: dict | None = None, timeout: float = 10, show: dict | None = None) -> None:
    """`ask(...)` without waiting: the request is sent now (in the order asked), and
    `then(answer)` runs at the engine's next turn after the answer (or no answer) comes.
    It counts as waiting (`waiting`) from now until then."""
    subject, request, answer = _request(channel, context, options, schema, show)
    with Asking._lock:
        Asking.out[channel] += 1

    def done(result: Any) -> None:
        with Asking._lock:
            Asking.out[channel] -= 1
        then(result)

    Asking.bus.request(subject, request, timeout, callback=lambda reply: Later.put(done, answer(reply)))


def waiting(channel: str) -> int:
    """How many questions to `channel` wait for an answer (asked with `ask_later`)."""
    return Asking.out[channel]


def _request(channel: str, context: str, options: Options, schema: dict | None,
             show: dict | None) -> tuple[str, dict, Callable[[dict | None], Any]]:
    """The subject, the request, and how to read its reply (see above)."""
    labelled = None if options is None else [list(o) if isinstance(o, tuple) else [o, None] for o in options]
    with Asking._lock:
        id = next(Asking._ids)
    request = {"id": id, "context": context, "options": labelled, "schema": schema, "show": show or {}}

    def answer(reply: dict | None) -> Any:
        if reply is None and channel == "usr":
            Asking.bus.publish(UI, {"type": "cancel", "id": id})  # too late: off the screen
        value = None if reply is None else reply.get("answer")
        if labelled is not None:
            ok = isinstance(value, int) and not isinstance(value, bool) and 0 <= value < len(labelled)
            return value if ok else None
        if schema is not None:
            return value
        return value if isinstance(value, str) and value.strip() else None

    return f"proki.ask.{channel}", request, answer
