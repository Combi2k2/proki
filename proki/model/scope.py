"""Scopes: where something is written, so its names can be found.

    global     inputs, and the global variables, signals and rules, and the programs' names
    program    suggest: its variables, signals and rules
    state      suggest.asking: its variables, signals and rules, and what its asks answer into

Everything is declared (`claim`) under its full name, the scope's prefix and its name:
`suggest.asking.answer`, so two states can both have an `answer`.

A name is found from the inside out, like in a programming language (`refer`): in state
asking of program suggest, `answer` is that state's if it has one, else the program's,
else the global one. So a name declared inside hides the one of the same name around it.
Nothing reaches into another program's or another state's scope. Only a reserved prefix
is dotted: a program in code keeps it for its own names, written as they are.

Every name in an expression is written out in full (`spell`) before it's compiled, so
what runs never needs to know about scopes.
"""

from __future__ import annotations

import ast
from typing import Any, ClassVar

from proki.errors import (
    ConfigError,
    ExprError
)


class Scope:
    """Where something is written: the global scope (`Scope()`), or one inside another."""

    RESERVED: ClassVar[set[str]] = set()   # the prefixes programs in code keep: their names dotted, never another's

    def __init__(self, name: str = "", outer: Scope | None = None):
        self.outer = outer
        self.names = set() if outer is None else outer.names                # every name declared, in full, in every scope

        self.prefix   = "" if outer is None else f"{outer.prefix}{name}."   # its variables' full names start with it
        self.prefixes = [self.prefix, *(outer.prefixes if outer else [])]   # where a name is looked for, innermost first

    def inner(self, name: str) -> Scope:
        """The scope of program or state `name`, inside this one."""
        return Scope(name, self)

    def claim(self, name: str) -> None:
        """Declare `name` here: new here, whatever it names (globally an input, a signal, a
        variable, a rule or a program). It may be one a scope around it has: here, it hides
        that one."""
        if self.taken(full := self.prefix + name):
            raise ConfigError(f"{name!r} is defined twice")
        if self.outer is None and name in self.RESERVED:
            raise ConfigError(f"{name!r} is reserved: its names are a program's")
        self.names.add(full)

    def taken(self, full: str) -> bool:
        """Whether the full name `full` is declared already."""
        return full in self.names

    def refer(self, name: Any) -> str | None:
        """The full name `name` means here, whatever it names: the state's, else the
        program's, else the global one. None if it's declared nowhere it's seen from here."""
        if not isinstance(name, str):  return None
        return next((full for prefix in self.prefixes if self.taken(full := prefix + name)), None)

    @staticmethod
    def reserve(*prefixes: str) -> None:
        """Keep `prefixes` for a program in code's own names: dotted, as they are."""
        Scope.RESERVED.update(prefixes)

    @staticmethod
    def reserved(node: ast.AST) -> bool:
        """Whether a node is a reserved prefix's name."""
        return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in Scope.RESERVED

    def spell(self, expr: Any) -> Any:
        """`expr` with its names written out in full, found from here outwards.

            "answer == 0"    →   "suggest.asking.answer == 0"   the state's, if it has one
            "total + 1"      →   "suggest.total + 1"            else the program's
            "count"          →   "count"                        else the global one

        A name found nowhere stays as written (compiling it says it's unknown), and so does
        anything that isn't text, and a reserved prefix's name. ExprError for any other dotted
        name: nothing reaches into another program's or state's scope."""
        if not isinstance(expr, str):
            return expr
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError:
            return expr

        nodes = list(ast.walk(tree))
        funcs = {id(node.func) for node in nodes if isinstance(node, ast.Call)}
        kept  = {id(node.value) for node in nodes if self.reserved(node)}   # a reserved prefix: as it is

        for node in nodes:
            if isinstance(node, ast.Attribute) and not self.reserved(node):
                raise ExprError(f"{expr!r}: not allowed in an expression: {ast.unparse(node)}")
            if isinstance(node, ast.Name):
                if id(node) in funcs | kept:  continue
                if full := self.refer(node.id):
                    node.id = full
        return ast.unparse(tree)
