"""Your programs, as tools: read them, and change them, each change checked before it's kept.
A spec is found by its fields, and a branch or an action by its place among its state's."""

from __future__ import annotations

from proki import editor, playground
from proki.engine import Engine
from proki.model import Spec
from proki.model.model import Model
from proki.programs.shipped import Shipped
from proki.tools.base import Tool

IDENT = {  # the fields a change finds its spec by
    "input"   : ("name",),
    "program" : ("name",),
    "variable": ("name", "scope", "program", "state"),
    "signal"  : ("name", "scope", "program", "state"),
    "rule"    : ("name", "scope", "program", "state"),
    "state"   : ("program", "name"),
    "branch"  : ("program", "state", "at"),
    "action"  : ("program", "state", "at"),
}
AT   = {"type": "integer", "minimum": 0, "description": "its place among its state's, from 0"}
NAME = {"anyOf": [{"type": "string"}, {"type": "null"}]}  # a program's, or null: the global scope


def tools(engine: Engine, shipped: Shipped) -> list[Tool]:
    """Reading the programs, changing several at once, switching and resetting one, then each
    kind's add, update and remove."""
    model: Model = engine.model
    made = [
        Tool("reference", "What a program can use (inputs, functions, actions, signals, variables, rules), "
                          "with their values now, and the programs that run.", {},
             lambda args: editor.reference(engine), readonly=True),
        Tool("evaluate", "An expression's value now, and its type, as an action would work it out (error: why it "
                         "can't be).", {"expr": {"type": "string"}},
             lambda args: editor.evaluate(args["expr"]), ("expr",), readonly=True),
        Tool("playground", "The playground's own made-up signals (a value a minute) and variables, to try on: with "
                           "`expr`, its value each minute and its type; with `action` (set, add, sub, append, remove), "
                           "taken at the last minute, the variables after it. `variables`: their values to start from "
                           "(else as shipped). Yours aren't seen there, and nothing of yours is set.",
             {"expr": {"type": "string"}, "action": {"type": "object"}, "variables": {"type": "object"}},
             lambda args: playground.play(args.get("expr"), args.get("action"), args.get("variables")), readonly=True),
        Tool("get_program", "One program, state by state as it's met from its initial one, and what it "
                            "depends on (`uses`).", {"name": {"type": "string"}},
             lambda args: editor.detail(engine, args["name"]), ("name",), readonly=True),
        Tool("list_specs", "The specs of a kind, as they're written (names short, found from their scope). "
                           "`program`: only that program's.", {"kind": {"type": "string", "enum": list(Spec.kinds)}, "program": {"type": "string"}},
             lambda args: model.all(**args), ("kind",), readonly=True),
        Tool("apply_changes", "Several changes, in order, checked once: all of them are kept, or none. Each is "
                              '{"op": add | update | remove, "kind": ..., "data": the arguments of that tool}.',
             {"changes": {"type": "array", "items": {"type": "object", "properties": {
                 "op": {"type": "string", "enum": ["add", "update", "remove"]}, "kind": {"type": "string", "enum": list(Spec.kinds)},
                 "data": {"type": "object"}}, "required": ["op", "kind", "data"]}}},
             lambda args: model.apply([(c["op"], c["kind"], c["data"]) for c in args["changes"]]), ("changes",)),
        Tool("unused", "What nothing depends on: each variable, signal and rule no program's way out depends on, "
                       "nor the app, nor a metric, down any chain, and each action that only sets them; as the "
                       "changes that take them out, as apply_changes takes them.", {},
             lambda args: {"changes": [{"op": op, "kind": kind, "data": data} for op, kind, data in editor.unused(engine)]}, readonly=True),
        Tool("remove_unused", "Takes out what nothing depends on (as `unused` lists it), checked once: all of it, or none.", {},
             lambda args: model.apply(editor.unused(engine))),
        Tool("program_specs", "One program's specs, each kind a list in order (a branch's or an action's place "
                              "among its state's, `at`, is its order there), or with name null the global scope's "
                              "(inputs, and the variables, signals and rules no program brings). `default`: proki "
                              "ships one, `changed`: yours differs from it.", {"name": NAME},
             lambda args: editor.specs(model, shipped, args["name"]), ("name",), readonly=True),
        Tool("switch_program", "A program on or off. Off, the cycles leave it alone; on again, it starts over.",
             {"name": {"type": "string"}, "on": {"type": "boolean"}},
             lambda args: engine.switch(args["name"], args["on"]), ("name", "on")),
        Tool("set_value", "A variable's value, set now, as an action would set it. Its full name: suggest.left, a "
                          "program's.", {"name": {"type": "string"}, "value": {}},
             lambda args: editor.set_value(args["name"], args.get("value")), ("name",)),
        Tool("reset_program", "A program back to its default, and what it brings (name null: the global "
                              "scope).", {"name": NAME},
             lambda args: shipped.revert(model, args["name"]), ("name",)),
    ]
    return made + [tool for kind, cls in Spec.kinds.items() for tool in of(model, kind, cls)]


def of(model: Model, kind: str, cls: type) -> list[Tool]:
    """A kind's add, update and remove, their arguments its spec's fields."""
    shape = cls.schema()
    ident = {key: shape["properties"].get(key, AT) for key in IDENT[kind]}
    if kind in Model.PLACED:
        shape["properties"]["at"] = {**AT, "description": "where it goes among its state's (last if left out)"}
    changes = {"type": "object", "properties": shape["properties"], "additionalProperties": {"not": {}}}
    found   = tuple(k for k in ident if k in ("name", "program", "at"))
    a       = "an" if kind[0] in "aeiou" else "a"
    return [
        Tool(f"add_{kind}",    f"Add {a} {kind}. {cls.DOCS}", shape["properties"],
             lambda args: model.add(kind, args), tuple(shape["required"])),
        Tool(f"update_{kind}", f"Change {a} {kind}, found by its fields: `changes` says the new values.", {**ident, "changes": changes},
             lambda args: model.update(kind, {k: v for k, v in args.items() if k != "changes"}, args["changes"]), (*found, "changes")),
        Tool(f"remove_{kind}", f"Remove {a} {kind}, found by its fields, and what it owns.", ident,
             lambda args: model.remove(kind, args), found, undoable=True),
    ]
