"""What the channels share: the bus, and the call that asks a channel and waits.

    answer = await request("jev", {"context": ..., "questions": ...}, timeout=10)

A request goes to the channel's subject ("proki.ask.jev"). Its worker answers with
{"answer": ...}, and `request` gives that answer. No answer is None: nobody is
subscribed, the call failed, or `timeout` seconds went by.
"""

from __future__ import annotations

import itertools
from collections import Counter
from typing import Any, ClassVar

from proki.services.nats import Bus, LocalBus


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
