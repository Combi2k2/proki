"""{"poke": {"text": "...", "values": {...}}}: a one-way message to you, through the UI. There's
nothing to answer: a question with options is the `ask` action (ask/)."""

from __future__ import annotations

from proki.core.actions.base import Action, check, evaluate
from proki.core.ui import Ui
from proki.errors import ActionError
from proki.utils import fill


class Poke(Action):
    def __init__(self, text: str, values: dict | None = None):
        if not isinstance(text, str) or not text:
            raise ActionError(f"poke: text is what to say ({text!r})")
        values = {} if values is None else values
        if not isinstance(values, dict):
            raise ActionError(f"poke: values are {{name: expr}} ({values!r})")
        self.text = text
        self.values = {str(name): str(expr) for name, expr in values.items()}
        for expr in self.values.values():
            check(expr)

    def apply(self) -> None:
        Ui.poke(fill(self.text, {name: evaluate(expr) for name, expr in self.values.items()}))

    def __repr__(self) -> str:
        return f"poke {self.text!r}"
