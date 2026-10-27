"""What the programs' tools show of your programs.

    specs(model, shipped, program)  one part of your programs, as its specs, as the app edits them
    reference(engine)               what a program can use, and what runs now, with its values
    detail(engine, name)            one program, state by state, and what it depends on
    evaluate(expr)                  an expression's value now, and its type
    set_value(name, value)          a variable's value, set now

A part is a program and what it brings, or the global scope (None: inputs, and the variables,
signals and rules no program brings).
"""

from __future__ import annotations

import inspect
from typing import Any

from proki.core.actions import ACTIONS
from proki.core.ops import FUNCTIONS
from proki.core.primitives import Primitive
from proki.core.programs import Program
from proki.core.records import Linked, Record, Records, reserved
from proki.core.rules import Rule
from proki.core.signals import Expr, Signal, Stream, Variable
from proki.engine import Engine
from proki.errors import ProkiError
from proki.model import Defaults, Model
from proki.programs.shipped import Shipped

STAMPED = {"id": "its id", "created_at": "when it was added (minutes since 1970)", "updated_at": "when it last changed (minutes since 1970)"}


def specs(model: Model, shipped: Shipped, program: str | None) -> dict:
    """One part of your programs, as its specs (in their order: a branch's or an action's place
    among its state's is its order there), each kind a list:

        program None (the global scope)   inputs, variables, signals, rules
        a program                         program (its spec), states, branches, actions,
                                          variables, signals, rules (its own, its
                                          states', and the global ones it brings)

    and `default`: whether it has one (yours, else proki's), `pinned`: whether it's yours,
    `changed`: whether it differs from it.
    KeyError for a program that isn't there."""
    if program is not None and all(p.name != program for p in model.specs.programs):
        raise KeyError(program)
    default = shipped.default(program)
    found   = {"default": default is not None, "pinned": Shipped.key(program) in shipped.pinned(),
               "changed": default is not None and Defaults.dump(default, program) != Defaults.dump(model.specs, program)}
    if program is None:
        return {**found, "inputs": model.all("input"),
                **{f"{kind}s": model.all(kind, program=None) for kind in ("variable", "signal", "rule")}}
    return {**found, "program": model.get("program", {"name": program}),
            **{Model.LISTS[kind]: model.all(kind, program=program)
               for kind in ("state", "branch", "action", "variable", "signal", "rule")}}


def reference(engine: Engine) -> dict:
    """What a program can use, and what runs now, with its values:

        inputs      every input: what it is, and whether the config reads it ("used")
        functions   what an expression can call
        actions     what a state's "do" can take: its params, and an example
        signals     every signal: global ones, programs' and states' (full names), their
                    expression, value, and history
        variables   the app state: global ones, programs' and states' (full names), the
                    programs' in code ("code"), a table's or a record's with its fields, and
                    the objects whose fields are variables of their own ("special")
        rules       every rule: global ones, programs' and states' (full names), and their
                    chance of firing now
        programs    every program: on or off, its state now, whether it's in the config or in
                    code (`kind`), and its tags

    Each input, signal, variable, rule and program says what it's for ("desc"); a signal or a
    variable the app reads says so ("app"), since it can't be removed or retyped."""
    compiled = engine.compiled
    used     = {i.name for i in compiled.inputs}
    declared = {v.name for v in compiled.variables}
    known    = {name: v.desc for name, v in Stream.registry.items()  # each object whose fields are variables of their own (track, work.plan)
                if isinstance(v, Linked) and any(other.startswith(f"{name}.") for other in Stream.registry)}
    return {
        "inputs"   : [{**input_row(name, kind), "used": name in used} for name, kind in Primitive.kinds.items()],
        "functions": [{"name": name, "call": kind.USAGE or name, "about": kind.ABOUT} for name, kind in FUNCTIONS.items()],
        "actions"  : [{"name": name, "about": kind.ABOUT, "example": kind.EXAMPLE,
                       "params": [n + ("" if p.default is inspect.Parameter.empty else "?") for n, p in inspect.signature(kind.__init__).parameters.items() if n != "self"]}
                      for name, kind in ACTIONS.items()],
        "signals"  : [{**signal_row(s), "scope": scope(s.name), "app": s.name in engine.reads} for s in compiled.signals],
        "variables": [*({**variable_row(v), "scope": scope(v.name), "from": "config" if v.name in declared else "code", "app": v.name in engine.reads, **columns(v)}
                        for v in Stream.registry.values() if isinstance(v, Variable) and v.name not in known
                        and under(v.name, known) is None and not v.name.startswith("_")),
                      *({"name": prefix, "desc": said, "value": None, "persist": False, "scope": "special", "from": "code",
                         "fields": [variable_row(v) | columns(v) for name, v in Stream.registry.items()
                                    if under(name, known) == prefix and isinstance(v, Variable) and not name.startswith("_")]}
                        for prefix, said in sorted(known.items()))],
        "rules"    : [{**rule_row(r), "scope": scope(r.name)} for r in Rule.registry.values()],
        "programs" : [{"name": p.name, "on": p.on, "state": p.current, "states": list(p.states),
                       "kind": "config" if p in compiled.programs else "code", "title": p.title, "desc": p.desc, "icon": p.icon, "tags": p.tags}
                      for p in Program.registry.values()],
    }


def detail(engine: Engine, name: str) -> dict:
    """One program, as its diagram shows it: its states in the order they're met from the
    initial one (each way out, in order, then the next state not met yet), each with

        do      its actions, as written (as made, for a program in code)
        every   minutes between tries of `next`
        vars    its own variables, and their values now
        next    its ways out, tried in order: `goto`, its conditions (each an expression
                and whether it's true now) and its rules (their sides, how soft, their
                level, the chance of firing now). Neither: the else

    and `uses`: what it depends on.

    The program, each state, way out, rule and variable say what they're for ("desc").
    Names are shown as written in the state: its own and its program's without their prefix.
    KeyError for a program that doesn't run."""
    program   = Program.registry[name]
    in_config = program in engine.compiled.programs
    written   = {s: [{a.kind: a.params} for a in engine.model.specs.actions if (a.program, a.state) == (name, s)]
                 for s in program.states} if in_config else {}
    order     = [program.initial]
    for state in order:  # breadth first: as the program meets them
        order += [b.goto for b in program.states[state].next if b.goto not in order]
    order += [s for s in program.states if s not in order]

    def shown(text: Any, state: str) -> Any:
        return text if not isinstance(text, str) else text.replace(f"{name}.{state}.", "").replace(f"{name}.", "")

    return {"name": name, "kind": "config" if in_config else "code", "on": program.on, "state": program.current,
            "initial": program.initial, "title": program.title, "desc": program.desc, "icon": program.icon, "tags": program.tags,
            "waking": program.wake[0].isoformat() if program.wake else None,
            "vars": [variable_row(v, shown(v.name, "")) for v in program.vars],
            "uses": uses(program, engine.compiled.signals),
            "states": [{"name" : state,
                        "desc" : body.desc,
                        "do"   : written[state] if in_config else [repr(action) for action in body.do],
                        "every": body.every.total_seconds() / 60,
                        "vars" : [variable_row(v, shown(v.name, state)) for v in body.vars],
                        "next" : [{"goto" : b.goto, "desc": b.desc,
                                   "conds": [{"expr": shown(c.expr, state), "value": value(c)} for c in b.conds],
                                   "rules": [rule_row(r, shown(r.name, state), shown(r.lhs.expr, state), shown(r.rhs.expr, state)) for r in b.rules]}
                                  for b in body.next]}
                       for state in order for body in [program.states[state]]]}


def uses(program: Program, signals: list[Signal]) -> dict:
    """What `program` depends on, a row each as in `reference`:

        rules       the rules its ways out vote with
        signals     the signals it reads, and the ones they read, ...
        variables   the ones it reads or sets ("sets": whether its actions change it), its
                    own and its states' among them
        inputs      the inputs all of these come down to

    A program in code shows only its own variables."""
    states = list(program.states.values())
    rules  = list(dict.fromkeys(r for s in states for b in s.next for r in b.rules))
    sets   = {v for s in states for a in s.do for v in a.write()}
    found  : dict[int, Stream] = {}
    todo   : list[Stream] = [
        *program.vars, *(v for s in states for v in s.vars), *sets,
        *(c for s in states for b in s.next for c in b.conds if isinstance(c, Stream)),  # a condition in code reads nothing shown
        *(side for r in rules for side in (r.lhs, r.rhs)),
        *(expr.stream() for s in states for a in s.do for expr in a.read()),
    ]
    while todo:  # everything they read, down to the inputs
        stream = todo.pop()
        if id(stream) not in found:
            found[id(stream)] = stream
            todo.extend(stream.inputs)
    named = {s.name for s in found.values() if Stream.registry.get(s.name) is s}
    own   = f"{program.name}."  # its own names, shown without it: suggest.asking.answer → asking.answer
    return {
        "rules"    : [rule_row(r, r.name.removeprefix(own)) for r in rules],
        "signals"  : [signal_row(s, s.name.removeprefix(own)) for s in signals if s.name in named],
        "variables": [{**variable_row(v, v.name.removeprefix(own)), "sets": v in sets} for v in Stream.registry.values()
                      if isinstance(v, Variable) and (v.name in named or v.name.startswith(own))],
        "inputs"   : [input_row(name, kind) for name, kind in Primitive.kinds.items() if name in named],
    }


def evaluate(expr: str) -> dict:
    """An expression's value now and its type, or why it has none."""
    try:
        made = Expr(expr).stream()
        return {"value": value(made), "type": typed(made)}
    except ProkiError as e:
        return {"error": str(e)}


def set_value(name: str, value: Any) -> dict:
    """A variable's value, set now (as an action would). KeyError for none of that name,
    VariableError for one read only, or a value not of its type."""
    found = Stream.registry[name]
    if not isinstance(found, Variable):
        raise KeyError(f"no variable {name!r}")
    found.set(value)
    return {}


# --- a row each --------------------------------------------------------------------------------

def input_row(name: str, kind: type[Primitive]) -> dict:
    """An input: what it is, its type, and its value now (None if the config doesn't read it)."""
    return {"name": name, "desc": kind.desc, "type": kind._typed, "value": value(Stream.registry.get(name))}


def signal_row(s: Signal, name: str | None = None) -> dict:
    """A signal: what it is, its expression, its type, its value now, how far back it keeps a table."""
    return {"name": name or s.name, "desc": s.desc, "expr": s.expr, "type": typed(s), "value": value(s),
            "backfill": s.window.total_seconds() / 60 if s.backfill and s.window else None, "persist": s.persist}


def variable_row(v: Variable, name: str | None = None) -> dict:
    """A variable: what it holds, its type, its value now, whether it's kept across restarts."""
    return {"name": name or v.name, "desc": v.desc, "type": typed(v), "value": value(v), "persist": v.persist}


def rule_row(r: Rule, name: str | None = None, lhs: str | None = None, rhs: str | None = None) -> dict:
    """A rule: what it's for, its sides, how soft, its level, the chance of firing now."""
    try:
        chance = None if Stream.now is None else float(r.chance())
    except Exception:
        chance = None
    return {"name": name or r.name, "desc": r.desc, "lhs": lhs or r.lhs.expr, "cmp": r.cmp, "rhs": rhs or r.rhs.expr,
            "softness": r.softness, "level": r.level, "chance": chance}


# --- what has fields ---------------------------------------------------------------------------

def columns(v: Variable) -> dict:
    """A table's or a record's fields, each with what it is (no value: each record has its own)."""
    if not isinstance(v, Records | Record):
        return {}
    table = v if isinstance(v, Records) else v.table
    descs = STAMPED | {k: f.desc for k, f in table.fields.items()} | {k: desc for k, (_, desc, _) in table.code.items()}
    types = table.type["items"]["properties"]
    return {"fields": [{"name": f"{v.name}.{k}", "desc": desc, "type": types[k], "value": None, "persist": False} for k, desc in descs.items()]}


def under(name: str, known: dict[str, str]) -> str | None:
    """The object a variable is a field of (None: none)."""
    return max((p for p in known if name.startswith(f"{p}.")), key=len, default=None)


# --- names and values --------------------------------------------------------------------------

def scope(name: str) -> str:
    """A variable's scope, from its full name: "global", "program" (suggest.left) or
    "state" (suggest.asking.answer). A reserved prefix's (work.task.score) is global."""
    if name.split(".")[0] in reserved():                                        return "global"
    if name.count(".") == 1 and name.split(".")[0] not in Program.registry:     return "global"  # a namespace's: session.active
    return ("global", "program", "state")[min(name.count("."), 2)]


def value(stream: Stream | None) -> Any:
    """A stream's value now, as JSON (None while it's unknown, or before the first cycle)."""
    if stream is None or Stream.now is None:
        return None
    try:
        v = stream.current()
    except Exception:
        return None
    v = v.item() if hasattr(v, "item") else v  # a number as a number, an object or a list as it is, anything else as text
    return v if v is None or isinstance(v, bool | str | int | float | dict | list) else str(v)


def typed(stream: Stream) -> Any:
    """A stream's type, as it says, else as worked out (any: one that can't be yet)."""
    try:
        return stream.type
    except Exception:
        return "any"
