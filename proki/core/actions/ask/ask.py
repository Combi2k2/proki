"""{"ask": {...}}: a question with options, to you ("usr"), jev ("jev") or an LLM ("llm").

    {"ask": {"channel": "usr",
             "context": "{h:.1f} h shallow so far. Start a session?",
             "values": {"h": "shallow_today / 60"},
             "options": [{"option": "Start", "criteria": "focus is building"}, {"option": "Not now"}],
             "result": "suggest_answer",
             "default": 1,
             "timeout": 120}}

It asks in the background (`ask_later`, core/ask.py), so the program goes on. The answer
comes back as the chosen option's index (0, 1, ...) in the variable `result`. While the
question waits, that variable is unknown, so rules on it don't pass yet. No answer
(dismissed, a failed call, nobody to ask, or past `timeout` seconds) is the `default`
index (-1: nothing chosen). The default timeout is 2 min for you, 10 s for jev and an LLM.

`values` are expressions, worked out when it's asked and filled into `context`
(`{h:.1f}`). `criteria` says what an option means, for jev and an LLM.

The state that asks decides where to go with its `next`, on the result:
`{"goto": "starting", "if": "suggest_answer == 0"}`.
"""

from __future__ import annotations

from proki.core.actions.base import Action, check, evaluate
from proki.core.ask import ask_later
from proki.core.signals import Stream, Variable
from proki.errors import ActionError
from proki.utils import fill

TIMEOUT = {"usr": 120, "jev": 10, "llm": 10}  # seconds, by channel


class Ask(Action):
    def __init__(self, channel: str, context: str, options: list, result: str, default: int,
                 timeout: float | None = None, values: dict | None = None):
        if channel not in TIMEOUT:
            raise ActionError(f"ask: channel is one of {', '.join(TIMEOUT)} ({channel!r})")
        if not isinstance(context, str) or not context:
            raise ActionError(f"ask: context is the question's text ({context!r})")
        values = {} if values is None else values
        if not isinstance(values, dict):
            raise ActionError(f"ask: values are {{name: expr}} ({values!r})")
        if not isinstance(options, list) or not options:
            raise ActionError("ask: options is a list of {option, criteria}")
        for entry in options:
            if not isinstance(entry, dict) or "option" not in entry or set(entry) - {"option", "criteria"}:
                raise ActionError(f"ask: an option is {{option, criteria}} ({entry!r})")
        labels = [str(entry["option"]) for entry in options]
        if len(set(labels)) != len(labels):
            raise ActionError(f"ask: an option is listed twice ({labels})")
        if isinstance(default, bool) or not isinstance(default, int) or not -1 <= default < len(labels):
            raise ActionError(f"ask: default is an option's index, -1 to {len(labels) - 1} ({default!r})")
        if timeout is not None and (isinstance(timeout, bool) or not isinstance(timeout, int | float) or timeout <= 0):
            raise ActionError(f"ask: timeout is in seconds, more than 0 ({timeout!r})")
        target = Stream.registry.get(result)
        if not isinstance(target, Variable):
            raise ActionError(f"ask: result is a variable, and there's none called {result!r}")
        self.channel, self.context, self.default = channel, context, default
        self.options = [(str(e["option"]), str(e["criteria"]) if e.get("criteria") else None) for e in options]
        self.values = {str(name): str(expr) for name, expr in values.items()}
        for expr in self.values.values():
            check(expr)
        self.timeout = TIMEOUT[channel] if timeout is None else timeout
        self.result = target

    def apply(self) -> None:
        self.result.set(None)  # unknown until the answer comes
        context = fill(self.context, {name: evaluate(expr) for name, expr in self.values.items()})
        ask_later(self.answered, self.channel, context, self.options, timeout=self.timeout)

    def answered(self, index: int | None) -> None:
        self.result.set(self.default if index is None else index)

    def __repr__(self) -> str:
        return f"ask {self.channel} {self.context!r} {[label for label, _ in self.options]} → {self.result.name}"
