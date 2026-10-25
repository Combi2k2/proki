"""Actions: what a program does as it enters a state, written as its kind, then its params.

    {"set": {"name": "pokes", "expr": "pokes + 1"}}

An action reads as Python does: `set` is `pokes := pokes + 1`, `add` is `pokes += 1`, an ask
is `answer := ask(...)`. What it reads names what's there already; what it sets is a variable,
or a place in one (`xs[0].status`), a name that's nobody's a new one.

An expression in an action is worked out as it's taken, so it can't hold a window
(`ts_mean(keys, 5)`): make the window a signal, and use its name.

What a question or a poke says is a text, or a format filled in as it's said:

    "context": "Start a session?"
    "context": {"format": "{h:.1f} h shallow so far. Start a session?", "values": {"h": "shallow_today / 60"}}
"""

from __future__ import annotations

import ast
import copy
import inspect
from collections.abc import Callable
from typing import Any, ClassVar

from proki.core.signals import Expr, Stream, Variable
from proki.errors import ActionError, VariableError
from proki.types import accept, field, itemof, typename
from proki.utils import fill, snake

Step = tuple[str, Any]   # ("field", its key) or ("item", its place, an RValue)

class RValue(Expr):
    """What an action reads: `pokes + 1`. ActionError for a window in it: `ts_mean(focus, 5)`."""
    def __new__(cls, text: Any) -> RValue:
        made = super().__new__(cls, text)
        if made.window is not None:
            raise ActionError(f"{made!r}: {made.window} keeps a window: use a signal's name")
        return made


class LValue(Expr):
    """What an action sets: a variable, `pokes`, or a place in one, `routines[0].bins[-1]`; a
    name that's nobody's, a new variable. ActionError for anything else."""

    def __new__(cls, text: Any) -> LValue:
        made = super().__new__(cls, text)
        made.variable, made.steps = made.trace()
        return made

    def read(self) -> list[RValue]:
        """The expressions it works out: `i`, of `xs[i]`."""
        return [at for step, at in self.steps if step == "item"]

    @property
    def type(self) -> Any:
        """The type it takes. ActionError for a column (xs.a), an item placed by anything but a number."""
        into = self.variable.type
        for step, at in self.steps:
            if step == "field" and typename(into) == "array":     raise ActionError(f"{self}: a field of a list is a column, which isn't set: an item's is")
            if step == "item" and not accept("number", at.type):  raise ActionError(f"{self}: an item's place is a number, {at} gives {typename(at.type)}")
            into = itemof(into) if step == "item" else field(into, at)
        return into

    def take(self, type: Any) -> None:
        """Values of `type` set into it: its variable's type, if it has none (a place's: checked once all's made)."""
        if not self.steps:
            try:
                self.variable.take(type)
            except VariableError as e:
                raise ActionError(str(e)) from None

    def set(self, value: Any) -> None:
        if not self.steps:
            return self.variable.set(value)
        self.apply(lambda old: value)

    def apply(self, change: Callable[[Any], Any]) -> None:
        """Its value from now on: `change` of what it is, the rest as it is (no such place: as it
        was). A record on the way, wherever it's held (item.status), is kept with it."""
        whole = copy.deepcopy(self.variable.current())
        trail = [whole]  # the values on the way down
        for step, at in self.steps:
            curr, at = trail[-1], at.value() if step == "item" else at
            try:
                if step == "field" and isinstance(curr, dict):   trail.append(curr.get(at))
                elif step == "item" and isinstance(curr, list):  trail.append(curr[at])
                else:                                            return
            except (IndexError, TypeError):  # no such place: xs[9] of 3, xs[1.5], xs[None]
                return
        if (new := change(trail[-1])) is trail[-1]:
            return
        if not self.steps:
            whole = new
        else:
            trail[-2][at] = new  # the last step's
            if row := next((at for at in reversed(trail[:-1]) if hasattr(at, "save")), None):
                row.save()  # the record it's in
        self.variable.set(whole)

    def trace(self) -> tuple[Variable, list[Step]]:
        """Its variable, and the way to its place there: the longest name there is, then fields and items."""
        from proki.core.programs import Program
        scopes = {"", *Program.registry, *(f"{name}.{state}" for name, p in Program.registry.items() for state in p.states)}
        node, steps = self.tree, []
        while not (isinstance(node, ast.Name | ast.Attribute) and ast.unparse(node) in Stream.registry):
            if isinstance(node, ast.Attribute):    steps, node = [("field", node.attr), *steps], node.value
            elif isinstance(node, ast.Subscript):  steps, node = [("item", RValue(ast.unparse(node.slice))), *steps], node.value
            elif isinstance(node, ast.Name) and all(s == "field" for s, _ in steps) and self.rpartition(".")[0] in scopes:
                return Variable(str(self)), []  # nobody's, a name alone in its scope (p.a.fresh, not p.a.fresh.x): a new one
            else:
                raise ActionError(f"no variable is called {self!r}")
        root = Stream.registry[ast.unparse(node)]
        if not isinstance(root, Variable):    raise ActionError(f"no variable is called {root.name!r}")
        if not getattr(root, "write", True):  raise ActionError(f"{root.name} is read only")  # kept by code, none to set it
        return root, steps


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
        self.values = {str(name): RValue(expr) for name, expr in values.items()}

    def said(self) -> str:
        """What it says now."""
        return fill(self.format, {name: expr.value() for name, expr in self.values.items()})

    def __repr__(self) -> str:
        return repr(self.format)
