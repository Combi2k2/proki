"""What the channels share: the bus, and the call that asks a channel and waits.

    answer = await request("jev", {"context": ..., "questions": ...}, timeout=10)

A request goes to the channel's subject ("proki.ask.jev"). Its worker answers with
{"answer": ...}, and `request` gives that answer. No answer is None: nobody is
subscribed, the call failed, or `timeout` seconds went by.

jev's and the LLM's answers are kept, the last few hundred, by what was asked: the same
question again is answered at once, from them, not asked (`fresh`: asked all the same).
No answer isn't kept, so it's asked again. Yours never are: you're asked each time.
"""

from __future__ import annotations

import itertools
import json
from collections import Counter, OrderedDict
from typing import Any, ClassVar

from proki.services.nats import Bus, LocalBus


class Channels:
    """The bus every channel talks on (the app sets it), and how many questions wait on each."""

    bus: ClassVar[Bus] = LocalBus()
    out: ClassVar[Counter] = Counter()  # questions waiting, by channel
    ids: ClassVar[itertools.count] = itertools.count(1)  # a question's id, to take it back (popup.py)
    kept: ClassVar[OrderedDict[str, Any]] = OrderedDict()  # the last answers kept, by what was asked, the latest last


KEEPS = ("jev", "llm")   # the channels whose answers are kept
KEPT  = 256              # answers kept, at most


async def request(channel: str, data: dict, timeout: float, fresh: bool = False) -> Any:
    """Ask `channel` and wait for its answer (None: no answer): a kept one, unless `fresh`."""
    asked = json.dumps([channel, data], sort_keys=True, default=str) if channel in KEEPS else None
    if asked in Channels.kept and not fresh:
        Channels.kept.move_to_end(asked)
        return Channels.kept[asked]
    Channels.out[channel] += 1
    try:
        reply = await Channels.bus.request(f"proki.ask.{channel}", data, timeout)
    finally:
        Channels.out[channel] -= 1
    answer = None if reply is None else reply.get("answer")
    if asked and answer is not None and not (isinstance(answer, str) and not answer.strip()):  # an empty text is none
        Channels.kept[asked] = answer
        Channels.kept.move_to_end(asked)
        while len(Channels.kept) > KEPT:
            Channels.kept.popitem(last=False)
    return answer


def queued(channel: str) -> int:
    """How many questions to `channel` wait for an answer."""
    return Channels.out[channel]
