"""Scopes: where something is written, so its names can be found.

    global     inputs, the global variables, signals and rules, and the programs' names
    program    suggest: its variables, signals and rules
    state      suggest.asking: its variables, signals and rules, and what its asks answer
               into, unless that's a name seen from there

Everything is declared (`claim`) under its full name, its scope's prefix then its name:
`suggest.asking.answer`, so two states can each have an `answer`.

A name is found from the inside out, as in Python (`refer`): in state asking of program
suggest, `answer` is that state's if it has one, else the program's, else the global one.
A name declared inside hides the one around it. Nothing reaches into another program's or
state's scope. A dot reads a field of a value (answer.hours), or a name the code keeps,
written as it is (work.task.estimate).

Every name in an expression is written out in full (`spell`) before it's compiled, so what
runs never needs to know about scopes.
"""

from __future__ import annotations

import ast
from typing import Any

from proki.core.records import reserved
from proki.errors import ConfigError, ExprError


class Scope:
    """Where something is written: the global scope (`Scope()`), or one inside another."""

    def __init__(self, name: str = "", outer: Scope | None = None):
        self.outer    = outer
        self.names    = set() if outer is None else outer.names                 # every name declared, in full, in every scope
        self.inners   = set() if outer is None else outer.inners                # every program's and state's, in full
        self.spaces   = reserved() if outer is None else outer.spaces           # the prefixes the code keeps
        self.prefix   = "" if outer is None else f"{outer.prefix}{name}."       # its names' full names start with it
        self.prefixes = [self.prefix, *(outer.prefixes if outer else [])]       # where a name is looked for, innermost first

    def inner(self, name: str) -> Scope:
        """The scope of program or state `name`, inside this one."""
        self.inners.add(self.prefix + name)
        return Scope(name, self)

    def claim(self, name: str) -> None:
        """Declare `name` here, whatever it names. It may hide one of a scope around it, never
        one of this scope, nor globally a name the code keeps."""
        if self.taken(full := self.prefix + name):      raise ConfigError(f"{name!r} is defined twice")
        if self.outer is None and name in self.spaces:  raise ConfigError(f"{name!r} is reserved: the code keeps its names")
        self.names.add(full)

    def taken(self, full: str) -> bool:
        """Whether the full name `full` is declared already."""
        return full in self.names

    def refer(self, name: Any) -> str | None:
        """The full name `name` means here: the state's, else the program's, else the global
        one (None: it's declared nowhere seen from here)."""
        if not isinstance(name, str):
            return None
        return next((full for prefix in self.prefixes if self.taken(full := prefix + name)), None)

    def spell(self, expr: Any) -> Any:
        """`expr` with its names written out in full, found from here outwards.

            "answer == 0"    →   "suggest.asking.answer == 0"   the state's, if it has one
            "total + 1"      →   "suggest.total + 1"            else the program's
            "count"          →   "count"                        else the global one
            "answer.hours"   →   "suggest.asking.answer.hours"  a field of a value: its name's

        A name found nowhere stays as written (compiling it says it's unknown), and so do a
        function, a name the code keeps, and anything that isn't an expression. ExprError for
        a dot into a program's or a state's scope (suggest.left)."""
        if not isinstance(expr, str):
            return expr
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError:
            return expr

        nodes = list(ast.walk(tree))
        funcs = {id(node.func) for node in nodes if isinstance(node, ast.Call)}
        dots  = [node for node in nodes if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)]
        kept  = {id(node.value) for node in dots if node.value.id in self.spaces} | funcs   # as they are

        if node := next((node for node in dots if id(node.value) not in kept and self.refer(node.value.id) in self.inners), None):
            raise ExprError(f"{expr!r}: not allowed in an expression: {ast.unparse(node)}")   # a program's or a state's: not a value

        for node in nodes:
            if isinstance(node, ast.Name) and id(node) not in kept and (full := self.refer(node.id)):
                node.id = full

        return ast.unparse(tree)
