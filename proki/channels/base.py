"""What the channels share:

    Question    what's sent, what its answer means, asked and waited for (`invoke`)
    request     a question sent on the bus, its answer waited for
    serve       a worker that answers a channel's questions, one at a time
    queued      how many questions to a channel wait

No answer is None: nobody answers, the call failed, or the time ran out. Answers are kept,
the last few hundred: the same question again is answered from them, unless it's `fresh`.
Yours never are: you're asked each time.
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter, OrderedDict
from collections.abc import Callable, Sequence
from typing import Any, ClassVar

from proki.services.nats import Bus, LocalBus
from proki.utils import numeric

Option  = tuple[str, str | None]
Options = Sequence[Option | str | list]


class Channels:
    """The bus every channel talks on (the app sets it), and how many questions wait on each."""

    bus: ClassVar[Bus] = LocalBus()
    out: ClassVar[Counter] = Counter()   # questions waiting, by channel


class Question:
    """A question to a channel: what's sent (`resolve_input`) and what its answer means
    (`resolve_output`), each channel's its own."""

    CHANNEL : ClassVar[str]
    KEEP    : ClassVar[bool] = True                             # whether its answers are kept
    KEPT    : ClassVar[int]  = 256                              # answers kept, at most, every question's together
    kept    : ClassVar[OrderedDict[str, Any]] = OrderedDict()   # the last answers kept, by what was asked, the latest last

    def __init__(self, context: str, timeout: float, fresh: bool = False):
        if not isinstance(context, str) or not context.strip():  raise ValueError(f"a question's context is a text ({context!r})")
        if not numeric(timeout) or timeout <= 0:                 raise ValueError(f"a question's timeout is in seconds, more than 0 ({timeout!r})")
        self.context, self.timeout, self.fresh = context, timeout, fresh

    async def invoke(self) -> Any:
        sent  = self.resolve_input()
        asked = json.dumps([self.CHANNEL, sent], sort_keys=True, default=str) if self.KEEP else None
        if asked in Question.kept and not self.fresh:
            Question.kept.move_to_end(asked)
            return self.resolve_output(Question.kept[asked])
        answer = await request(self.CHANNEL, sent, self.timeout)
        if asked and (text(answer) if isinstance(answer, str) else answer) is not None:
            Question.kept[asked] = answer
            Question.kept.move_to_end(asked)
            while len(Question.kept) > Question.KEPT:
                Question.kept.popitem(last=False)
        return self.resolve_output(answer)

    def resolve_input(self) -> dict:
        return {"context": self.context}

    def resolve_output(self, answer: Any) -> Any:
        return answer


async def request(channel: str, data: dict, timeout: float) -> Any:
    """Ask `channel` and wait for its answer (None: no answer)."""
    Channels.out[channel] += 1
    try:
        reply = await Channels.bus.request(f"proki.ask.{channel}", data, timeout)
    finally:
        Channels.out[channel] -= 1
    return None if reply is None else reply.get("answer")


async def serve(bus: Bus, channel: str, handler: Callable[[dict], Any]) -> None:
    """Answer `channel` with `handler` of each request, on a thread: a failed call is no answer."""
    async def handle(request: dict) -> dict:
        try:
            return {"answer": await asyncio.to_thread(handler, request)}
        except Exception:
            return {"answer": None}

    await bus.subscribe(f"proki.ask.{channel}", handle, workers=1)


def queued(channel: str) -> int:
    """How many questions to `channel` wait for an answer."""
    return Channels.out[channel]


def paired(options: Options) -> list[Option]:
    """Each option as (label, what it means). ValueError for one that's neither."""
    made = []
    for option in options:
        if isinstance(option, str):
            made.append((option, None))
        elif (isinstance(option, tuple | list) and len(option) == 2
              and isinstance(option[0], str) and (option[1] is None or isinstance(option[1], str))):
            made.append((option[0], option[1]))
        else:
            raise ValueError(f"an option is a text, or [text, what it means] ({option!r})")
    return made


def text(answer: Any) -> str | None:
    """The answer, if it's a text that isn't blank (None: else)."""
    return answer if isinstance(answer, str) and answer.strip() else None
