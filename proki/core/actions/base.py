"""The base of every action, and the two helpers actions use for their expressions.

What an action is: one step a program takes when it enters a state (core/programs.py),
such as setting a variable, asking a question, or ringing an alarm. An action only does
its step. It doesn't know which program or state it's in, and it never moves the program
(that's the state's `next`).

How the config writes one: its kind, then its params by name.

    {"set": {"name": "pokes", "expr": "pokes + 1"}}

    kind     "set": the class's name in snake case (`Set` → "set", `Poke` → "poke")
    params   the keyword arguments of the class's `__init__`, so this entry becomes
             Set(name="pokes", expr="pokes + 1")

Writing a new kind is defining a subclass: it's registered in `Action.kinds` under its
snake-case name, and its `__init__` arguments are its params. No list of fields to keep
in sync.

Expressions in actions: an action works out its expressions once, at the moment it's
taken (`evaluate`). So an expression in an action can't contain a window like
`ts_mean(keys, 5)`, which needs to see every cycle to have a value. `check` rejects that
when the config is compiled. The fix is to make the window a signal and use the signal's
name in the action.
"""

from __future__ import annotations

import inspect
from typing import Any, ClassVar

from proki.core.signals import Stream, compile_expr
from proki.utils import snake
from proki.errors import ActionError


class Action:
    """One step a program takes when it enters a state.

    Each kind is a subclass. Its config name is its class name in snake case, its params
    are its `__init__`'s keyword arguments, and `apply` takes the step.
    """

    kinds: ClassVar[dict[str, type[Action]]] = {}  # every kind, by its name in the config

    def __init_subclass__(cls, **kwargs: Any):
        """Register the new kind by its snake-case name (`Poke` → "poke")."""
        super().__init_subclass__(**kwargs)
        Action.kinds[snake(cls.__name__)] = cls

    def apply(self) -> None:
        """Take the step, now. Each kind says what that is."""
        raise NotImplementedError

    @classmethod
    def parse(cls, entry: dict) -> Action:
        """The action a config entry describes.

            {"set": {"name": "x", "expr": "1"}}   →   Set(name="x", expr="1")

        Before calling the class, the params are checked against what its `__init__`
        takes, so a mistake reads like the config, not like Python:

            {"set": {"name": "x"}}                →   set takes {name, expr}: missing expr
            {"set": {"nme": "x", "expr": "1"}}    →   set takes {name, expr}: unknown nme

        Raises ActionError for an unknown kind or wrong params."""
        if not isinstance(entry, dict) or len(entry) != 1 or (kind := next(iter(entry))) not in cls.kinds:
            raise ActionError(f"an action is one of {', '.join(sorted(cls.kinds))} ({entry})")
        made, params = cls.kinds[kind], entry[kind]
        signature = inspect.signature(made.__init__)
        names = [p for p in signature.parameters if p != "self"]
        required = [p for p in names if signature.parameters[p].default is inspect.Parameter.empty]
        takes = f"{kind} takes {{{', '.join(names)}}}"

        if not isinstance(params, dict):            raise ActionError(f"{takes} ({params!r})")
        if unknown := set(params) - set(names):     raise ActionError(f"{takes}: unknown {', '.join(sorted(unknown))}")
        if missing := set(required) - set(params):  raise ActionError(f"{takes}: missing {', '.join(sorted(missing))}")
        return made(**params)


def check(expr: str) -> None:
    """Make sure an action's expression can be worked out at any moment, when the config
    is compiled. Raises ExprError for a name that isn't defined, and ActionError for a
    window (`ts_mean`, `delay`, `every`, ...), which needs every cycle.

    Names of signals, variables and inputs are fine, even if they hold a window
    themselves: they move on every cycle on their own. Only arithmetic, comparisons and
    constants may sit around them."""
    from proki.core.ops import Constant, Lift

    def walk(stream: Stream) -> None:
        if stream.name and Stream.registry.get(stream.name) is stream:
            return  # a named stream: it moves on every cycle anyway
        if not isinstance(stream, Lift | Constant):
            raise ActionError(f"{expr!r}: {snake(type(stream).__name__)} keeps a window, which an action "
                             f"works out on the spot can't: make it a signal and use its name")
        for i in stream.inputs:
            walk(i)

    walk(compile_expr(expr))


def evaluate(expr: str) -> Any:
    """The expression's value at this moment (None if unknown). Used by actions as they're taken."""
    return compile_expr(expr).current()
