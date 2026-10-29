"""Actions on a variable, by an expression's value as it's taken:

    {"set": {"name": "deadline_eod", "expr": "deadline_eod + 1440"}}      to the value
    {"add": {"name": "active_today", "expr": "active"}}                    the value added (true: 1)
    {"sub": {"name": "budget", "expr": "minutes"}}                         the value taken away
    {"add": {"name": "routines[0].bins[daytime // 60]", "expr": "1"}}      at a place in it (-1: the last)
    {"set": {"name": "item.status", "expr": "'done'"}}                     a record's field, the record's own too
    {"append": {"name": "work.groups", "expr": {"name": "'Thesis'"}}}      an item added to a list: an object, its
    {"append": {"name": "deadlines", "expr": "time + 60"}}                 fields each an expression, or the value
    {"remove": {"name": "notes", "id": "todo.id"}}                         the item with that id taken out
    {"set": {"name": "x", "expr": "1", "when": "answer == 2"}}             only if it's true

An unknown value or id changes nothing, nor does anything at a place that isn't there. A value is a copy: with x = xs[0], setting x.a changes x, not xs.
"""

from __future__ import annotations

from typing import ClassVar

from proki.core.actions.base import Action, LValue, RValue
from proki.core.signals import Variable
from proki.errors import ActionError, ExprError
from proki.types import accept, field, itemof, typename
from proki.utils import snake


class Update:
    """The variable `name`, or a place in it, changed by `expr`'s value (see above), if `when`.
    Each kind applies it as it says: the value set, added, taken away."""

    READS: ClassVar[bool] = True  # x += expr: x is there already (set, x := expr: it needn't be)

    def __init__(self, name: LValue, expr: RValue | None, when: RValue | None = None):
        self.expr = None if expr is None else RValue(expr)  # null: unknown
        self.when = None if when is None else RValue(when)
        if self.READS:
            try:
                RValue(name)
            except ExprError:
                raise ActionError(f"{self.kind}: no variable is called {str(name)!r}") from None
        self.name = LValue(name)

    @property
    def kind(self) -> str:
        return snake(type(self).__name__)

    def read(self) -> list[RValue]:
        return [e for e in (self.when, self.expr, *self.name.read()) if e is not None]

    def write(self) -> list[Variable]:
        return [self.name.variable]

    def typecheck(self) -> None:
        """ActionError unless the value goes in: numbers, to add or take away (true or false: 1 or 0)."""
        into, given = self.name.type, None if self.expr is None else self.expr.type
        if given is not None and not (accept("number", into) and (given == "boolean" or accept("number", given))):
            raise ActionError(f"{self.kind}: adds and subtracts numbers ({self.name} is of type {typename(into)}, {self.expr} gives {typename(given)})")

    def __repr__(self) -> str:
        return f"{self.kind} {self.name} by {self.expr}"


class Set(Update, Action):
    ABOUT   = "set a variable, or a field or an item of one, to an expression's value"
    EXAMPLE = {"set": {"name": "deadline_eod", "expr": "deadline_eod + 1440"}}
    READS   = False

    async def apply(self) -> None:
        if self.when is None or self.when.value():
            self.name.set(None if self.expr is None else self.expr.value())  # a variable kept by code is told even of the value it has

    def typecheck(self) -> None:
        if self.expr is not None and not accept(into := self.name.type, given := self.expr.type):
            raise ActionError(f"set: {self.name} is of type {typename(into)}, {self.expr} gives {typename(given)}")


class Add(Update, Action):
    ABOUT   = "add an expression's value to a variable, or a field or an item of one (true / false add 1 / 0)"
    EXAMPLE = {"add": {"name": "active_today", "expr": "active"}}

    async def apply(self) -> None:
        if (self.when is None or self.when.value()) and self.expr is not None and (value := self.expr.value()) is not None:
            self.name.apply(lambda old: old if old is None else old + value)


class Sub(Update, Action):
    ABOUT   = "take an expression's value from a variable, or a field or an item of one"
    EXAMPLE = {"sub": {"name": "budget", "expr": "minutes"}}

    async def apply(self) -> None:
        if (self.when is None or self.when.value()) and self.expr is not None and (value := self.expr.value()) is not None:
            self.name.apply(lambda old: old if old is None else old - value)


class Append(Update, Action):
    ABOUT   = "add an item to a list: an expression's value, or an object, each of its fields an expression's value"
    EXAMPLE = {"append": {"name": "work.groups", "expr": {"name": "'Thesis'"}}}
    READS   = False

    def __init__(self, name: LValue, expr: RValue | dict[str, RValue], when: RValue | None = None):
        if isinstance(expr, dict) and not expr:
            raise ActionError("append: an object has fields, {field: expr}, the new item's ({})")
        super().__init__(name, None if isinstance(expr, dict) else expr, when)
        self.fields = {str(k): RValue(v) for k, v in expr.items()} if isinstance(expr, dict) else None

    async def apply(self) -> None:
        if self.when is None or self.when.value():
            made = {k: e.value() for k, e in self.fields.items()} if self.fields is not None else None if self.expr is None else self.expr.value()
            if made is not None:
                self.name.apply(lambda items: [*(items or []), made])

    def read(self) -> list[RValue]:
        return [*super().read(), *(self.fields or {}).values()]

    def typecheck(self) -> None:
        into = self.name.type
        if typename(into) not in ("array", "any"):  raise ActionError(f"append: {self.name} isn't a list ({typename(into)})")
        item = itemof(into)
        if self.fields is None:
            if self.expr is not None and not accept(item, given := self.expr.type):
                raise ActionError(f"append: {self.name}'s items are of type {typename(item)}, {self.expr} gives {typename(given)}")
            return
        if typename(item) not in ("object", "any"):  raise ActionError(f"append: {self.name}'s items are of type {typename(item)}, not objects with fields")
        for key, expr in self.fields.items():
            if not accept(field(item, key), given := expr.type):
                raise ActionError(f"append: {self.name}'s {key} is of type {typename(field(item, key))}, {expr} gives {typename(given)}")

    def __repr__(self) -> str:
        return f"append {self.name} {self.expr if self.fields is None else self.fields}"


class Remove(Update, Action):
    ABOUT   = "take an item out of a list: the one with an expression's value as its id"
    EXAMPLE = {"remove": {"name": "notes", "id": "todo.id"}}
    READS   = False

    def __init__(self, name: LValue, id: RValue, when: RValue | None = None):
        super().__init__(name, None, when)
        self.which = RValue(id)  # not `id`: an action's own, the builder's

    async def apply(self) -> None:
        if (self.when is None or self.when.value()) and (gone := self.which.value()) is not None:
            self.name.apply(lambda items: [item for item in items or [] if not (isinstance(item, dict) and dict.get(item, "id") == gone)])

    def read(self) -> list[RValue]:
        return [*super().read(), self.which]

    def typecheck(self) -> None:
        into = self.name.type
        if typename(into) not in ("array", "any"):                   raise ActionError(f"remove: {self.name} isn't a list ({typename(into)})")
        if typename(item := itemof(into)) not in ("object", "any"):  raise ActionError(f"remove: {self.name}'s items are of type {typename(item)}, not objects with an id")
        if not accept(field(item, "id"), given := self.which.type):
            raise ActionError(f"remove: {self.name}'s ids are of type {typename(field(item, 'id'))}, {self.which} gives {typename(given)}")

    def __repr__(self) -> str:
        return f"remove {self.name} id {self.which}"
