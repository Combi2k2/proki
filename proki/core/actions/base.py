"""Actions: what a program does as it enters a state, written as its kind, then its params.

    {"set": {"name": "pokes", "expr": "pokes + 1"}}

An expression in an action is worked out as it's taken, so it can't hold a window
(`ts_mean(keys, 5)`): make the window a signal, and use its name.

What a question or a poke says is a text, or a format filled in as it's said:

    "context": "Start a session?"
    "context": {"format": "{h:.1f} h shallow so far. Start a session?", "values": {"h": "shallow_today / 60"}}
"""

from __future__ import annotations

import inspect
from typing import Any, ClassVar

from proki.core.signals import Expr, Variable
from proki.errors import ActionError
from proki.utils import fill, snake


class InstantExpr(Expr):
    """An expression worked out at once: ActionError for a window in it, `focus_5m`, not `ts_mean(focus, 5)`."""

    def __new__(cls, text: Any) -> InstantExpr:
        made = super().__new__(cls, text)
        if not made.rvalue:
            raise ActionError(f"{made!r}: {made.window} keeps a window: use a signal's name")
        return made

    @property
    def rvalue(self) -> bool:
        """Whether it has no window."""
        return self.window is None


class Action:
    """An action: {"set": {"name": "pokes", "expr": "pokes + 1"}} is Set(name="pokes", expr="pokes + 1")."""

    # a kind is a subclass, called by its name in snake case, its params its __init__'s
    kinds   : ClassVar[dict[str, type[Action]]] = {}   # every kind, by its name
    ABOUT   : ClassVar[str] = ""                       # what it does, in a line, for the editor
    EXAMPLE : ClassVar[dict | None] = None             # and one, as it's written
    id      : str | None = None                        # given by the builder

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        Action.kinds[snake(cls.__name__)] = cls

    async def apply(self) -> None:
        """Does it (a question: once it's answered)."""
        raise NotImplementedError

    def read(self) -> list[Expr]:
        """The expressions it works out."""
        return []

    def write(self) -> list[Variable]:
        """The variables it changes."""
        return []

    def typecheck(self) -> None:
        """ActionError for a value of a type its variable doesn't take."""

    @classmethod
    def parse(cls, entry: dict) -> Action:
        """The action written: {"set": {"name": "x"}} → ActionError: set takes {name, expr}: missing expr."""
        if not isinstance(entry, dict) or len(entry) != 1 or (kind := next(iter(entry))) not in cls.kinds:
            raise ActionError(f"an action is one of {', '.join(sorted(cls.kinds))} ({entry})")
        made, params = cls.kinds[kind], entry[kind]
        signature = inspect.signature(made.__init__)
        names = [p for p in signature.parameters if p != "self"]
        takes = f"{kind} takes {{{', '.join(names)}}}"
        required = [p for p in names if signature.parameters[p].default is inspect.Parameter.empty]

        if not isinstance(params, dict):            raise ActionError(f"{takes} ({params!r})")
        if unknown := set(params) - set(names):     raise ActionError(f"{takes}: unknown {', '.join(sorted(unknown))}")
        if missing := set(required) - set(params):  raise ActionError(f"{takes}: missing {', '.join(sorted(missing))}")
        return made(**params)


class Context:
    """What a question or a poke says (see above)."""

    def __init__(self, spec: Any, kind: str):
        spec = {"format": spec} if isinstance(spec, str) else spec
        format = spec.get("format") if isinstance(spec, dict) else None
        values = spec.get("values", {}) if isinstance(spec, dict) else None

        if not isinstance(spec, dict) or set(spec) - {"format", "values"}:
            raise ActionError(f"{kind}: context is a text, or {{format, values}} ({spec!r})")
        if not isinstance(format, str) or not format:   raise ActionError(f"{kind}: context's format is what's said ({format!r})")
        if not isinstance(values, dict):                raise ActionError(f"{kind}: context's values are {{name: expr}} ({values!r})")

        self.format = format
        self.values = {str(name): InstantExpr(expr) for name, expr in values.items()}

    def said(self) -> str:
        """What it says now."""
        return fill(self.format, {name: expr.value() for name, expr in self.values.items()})

    def __repr__(self) -> str:
        return repr(self.format)
