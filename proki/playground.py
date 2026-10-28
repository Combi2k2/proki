"""The playground: made-up signals and variables of proki's own, to try expressions and actions
on without touching yours.

    play(expr, action, variables)   its signals, a value a minute; an expression's value each
                                    minute; an action taken at the last one; its variables after

Its names are its own: yours aren't seen there, and nothing of yours is set.
"""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

from proki import settings
from proki.core.actions import Action
from proki.core.signals import Expr, Stream, Variable
from proki.editor import typed, value
from proki.errors import ActionError
from proki.types import typeof

SMOKE = settings.ASSETS_DIR / "smoke.json"            # its signals and variables, as shipped
KINDS = ("set", "add", "sub", "append", "remove")      # the actions it takes: a variable's
STEP  = timedelta(minutes=1)                           # between two of a signal's values
START = datetime(2000, 1, 1, 9, tzinfo=timezone.utc)   # its first minute (its clock's: "start")


def play(expr: str | None = None, action: dict | None = None, variables: dict[str, Any] | None = None) -> dict:
    """Its `signals` (each `desc` and `values`, a minute apart from `start`), and its `variables`
    (each `desc`, `type` and `value`): as shipped, or `variables`' values. With `expr`: its `values`, one a
    minute, and its `type`. With `action` (set, add, sub, append, remove): taken at the last
    minute, the variables then. ProkiError for a mistake in either."""
    shipped = json.loads(SMOKE.read_text())
    given   = variables or {}
    held    = Stream.registry, Stream.now, Stream.live
    Stream.registry, Stream.live = {}, None
    try:
        signals = []
        for name, s in shipped["signals"].items():
            made = Stream()  # given its values, never worked out
            made.name, made.desc, made.period, made._typed = name, s["desc"], STEP, "number"
            made._playback = deque((START + i * STEP, v) for i, v in enumerate(s["values"]))
            Stream.registry[name] = made
            signals.append(made)
        descs = {name: v["desc"] for name, v in shipped["variables"].items()}
        for name, v in {**{n: v["value"] for n, v in shipped["variables"].items()}, **given}.items():
            Variable(name, None, descs.get(name, ""), type=typeof(v)).set(v)
        made, said = Expr(expr).stream() if expr else None, []
        for i in range(max(len(s["values"]) for s in shipped["signals"].values())):
            Stream.tick(START + i * STEP, [*signals, *([made] if made else [])])
            said.append(value(made))
        if action:
            if next(iter(action), None) not in KINDS:
                raise ActionError(f"an action here is one of {', '.join(KINDS)} ({action})")
            taken = Action.parse(action)
            taken.typecheck()
            step = taken.apply()  # never waits: a variable's
            try:
                step.send(None)
            except StopIteration:
                pass
        return {"start": shipped["start"], "signals": shipped["signals"],
                "variables": {v.name: {"desc": descs.get(v.name, v.desc), "type": typed(v), "value": value(v)} for v in Stream.registry.values() if isinstance(v, Variable)},
                **({"values": said, "type": typed(made)} if made else {})}
    finally:
        Stream.registry, Stream.now, Stream.live = held
