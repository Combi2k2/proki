"""{"ask": {...}}: ask you, jev or an LLM, and keep the answer in a variable of the state:
the option picked, or a text.

    {"ask": {
        "channel": "usr",
        "context": {"format": "{h:.1f} h shallow so far. Start a session?", "values": {"h": "shallow_today / 60"}},
        "options": [{"option": "Start", "criteria": "focus is building"}, {"option": "Not now"}],
        "result":  "$answer",
        "default": 1,
        "timeout": 120
    }}

    channel   who answers: "usr" (you, in the popup), "jev" or "llm"
    context   the question: a text, or {format, values} to fill values in as it's asked
              (actions/base.py)
    options   what can be picked. `criteria` tells jev and an LLM what an option means.
              Without options, the answer is a text: what you type, or what the LLM
              writes (jev only picks options)
    result    the state's variable the answer goes into, made without declaring it ("$answer"
              or "answer"): the picked option's index (0, 1, ...), or the text
    default   with options, the index when there's no answer (optional, -1: nothing picked).
              A text without an answer is unknown
    timeout   how many seconds to wait (optional): 120 for you, 10 for jev and an LLM

No answer means it was dismissed, the call failed, nobody was there to ask, or `timeout`
went by. While the question waits, `result` is unknown. Only this program waits, the
others go on.

The state that asks moves on with its `next`, by the result:

    "next": [{"goto": "starting", "if": "$answer == 0"}]

A text goes on to another question through its context's values:

    {"ask": {"channel": "jev", "context": {"format": "A note someone wrote: {note}", "values": {"note": "$text"}}, ...}}

To keep it for another state, `set` a variable of the program to it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import ClassVar

from proki.core.actions.base import Action, Context
from proki.core.signals import Stream, Variable
from proki.errors import ActionError

# seconds to wait, by channel
TIMEOUT = {
    "usr": 120,
    "jev": 10,
    "llm": 10,
}

# how a channel is asked: (context, options as (label, criteria) or None, timeout) → the
# picked option's index, or the text without options (None: no answer)
Pick = Callable[[str, list[tuple[str, str | None]] | None, float], Awaitable[int | str | None]]


class Ask(Action):
    # who answers each channel, set by the app (None: nobody, so the answer is the default)
    ask_usr: ClassVar[Pick | None] = None
    ask_jev: ClassVar[Pick | None] = None
    ask_llm: ClassVar[Pick | None] = None

    def __init__(self, channel: str, context: str | dict, result: str, options: list | None = None, default: int | None = None, timeout: float | None = None):
        target = Stream.registry.get(result)  # the state's, by its full name (the compiler made it)

        if channel not in TIMEOUT:                              raise ActionError(f"ask: channel is one of {', '.join(TIMEOUT)} ({channel!r})")
        if not isinstance(target, Variable):                    raise ActionError(f"ask: result is the name of a variable for the answer ({result!r})")
        if options is None and channel == "jev":                raise ActionError("ask: jev only picks options, so it needs some")
        if options is None and default is not None:             raise ActionError("ask: default is an option's index, so it needs options")
        if options is not None and (not isinstance(options, list) or not options):
            raise ActionError("ask: options is a list of {option, criteria}")

        for entry in options or []:
            if not isinstance(entry, dict) or "option" not in entry or set(entry) - {"option", "criteria"}:
                raise ActionError(f"ask: an option is {{option, criteria}} ({entry!r})")

        labels = [str(entry["option"]) for entry in options or []]
        default = -1 if options is not None and default is None else default
        if len(set(labels)) != len(labels):
            raise ActionError(f"ask: an option is listed twice ({labels})")
        if options is not None and (isinstance(default, bool) or not isinstance(default, int) or not -1 <= default < len(labels)):
            raise ActionError(f"ask: default is an option's index, -1 to {len(labels) - 1} ({default!r})")
        if timeout is not None and (isinstance(timeout, bool) or not isinstance(timeout, int | float) or timeout <= 0):
            raise ActionError(f"ask: timeout is in seconds, more than 0 ({timeout!r})")

        self.channel = channel
        self.context = Context(context, "ask")
        self.options = None if options is None else [(label, str(e["criteria"]) if e.get("criteria") else None) for label, e in zip(labels, options)]
        self.result = target
        self.default = default
        self.timeout = TIMEOUT[channel] if timeout is None else timeout

    def reads(self) -> list[str]:
        return list(self.context.values.values())

    def writes(self) -> list[Variable]:
        return [self.result]

    async def apply(self) -> None:
        self.result.set(None)  # unknown until the answer comes
        picker = getattr(Ask, f"ask_{self.channel}")
        answer = None if picker is None else await picker(self.context.said(), self.options, self.timeout)
        self.result.set(self.default if answer is None else answer)

    def __repr__(self) -> str:
        options = "text" if self.options is None else [label for label, _ in self.options]
        return f"ask {self.channel} {self.context!r} {options} → {self.result.name}"

