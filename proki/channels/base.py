"""What the channels share: the bus, and the call that asks a channel and waits.

    answer = await request("jev", {"context": ..., "questions": ...}, timeout=10)

A request goes to the channel's subject ("proki.ask.jev"). Its worker answers with
{"answer": ...}, and `request` gives that answer. No answer is None: nobody is
subscribed, the call failed, or `timeout` seconds went by.
"""

from __future__ import annotations

import itertools
from collections import Counter
from collections.abc import Sequence
from typing import Any, ClassVar

from proki.services.nats import Bus, LocalBus

Options = Sequence[str | tuple[str, str | None]]  # "Start", or ("Start", what it means)


class Channels:
    """The bus every channel talks on (the app sets it), and how many questions wait on each."""

    bus: ClassVar[Bus] = LocalBus()
    out: ClassVar[Counter] = Counter()  # questions waiting, by channel
    ids: ClassVar[itertools.count] = itertools.count(1)  # a question's id, to take it back (popup.py)


async def request(channel: str, data: dict, timeout: float) -> Any:
    """Ask `channel` and wait for its answer (None: no answer)."""
    Channels.out[channel] += 1
    try:
        reply = await Channels.bus.request(f"proki.ask.{channel}", data, timeout)
    finally:
        Channels.out[channel] -= 1
    return None if reply is None else reply.get("answer")


def queued(channel: str) -> int:
    """How many questions to `channel` wait for an answer."""
    return Channels.out[channel]


def paired(options: Options) -> list[list]:
    """Each option as [label, criteria] ("Start" becomes ["Start", None])."""
    return [list(o) if isinstance(o, tuple) else [o, None] for o in options]


def picked(answer: Any, options: list) -> int | None:
    """`answer` if it's the index of one of `options`, else None."""
    return answer if isinstance(answer, int) and not isinstance(answer, bool) and 0 <= answer < len(options) else None
