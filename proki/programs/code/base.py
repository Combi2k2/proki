"""What a program in code is made of, and how it reaches the rest.

    Ritual(name, states)        a program in states, as a config one is
    Step                        an action in Python, with its program at hand
    make_branch(goto, **when)   a way out of a state, taken when all of `when` are true now
    make_variable(name, value)  a variable, starting at `value` (the one there is, if any)
    find_variable(name)         a variable, by name (ConfigError if there's none)

    choose(context, options)    a question whose options each mean something to the program
    popup_open()                whether a question waits for you

    Table[Row]                  a table of proki.db, a row for each `Row` (a dataclass)

A step keeps what it found on its program, and the ways out read it there:

    State("waiting", do=[Look(self)], every=timedelta(minutes=1), next=[
        make_branch("reminding", due=lambda: self.item is not None),
        make_branch("waiting"),
    ])
"""

from __future__ import annotations

import inspect
import json
import types
import typing
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import astuple, fields
from datetime import UTC, datetime
from enum import Enum
from typing import Any, ClassVar, Generic, TypeVar

from proki.channels import Popup, queued
from proki.core.actions import Action
from proki.core.programs import Branch, Program, State
from proki.core.signals import Stream, Variable
from proki.errors import ConfigError
from proki.utils import snake


class Ritual(Program):
    """A program in code, laid out in states as a config one is.

        name        its name, "@" first ("@planner")
        states      its states (none: a single one, "on")
        initial     the state it starts in (None: the first)

        DESC        what it's for (empty: its module's first paragraph)
        TAGS        its tags
    """

    RESERVED = "@"

    DESC: ClassVar[str]             = ""
    TAGS: ClassVar[tuple[str, ...]] = ()

    def __init__(self, name: str, states: Iterable[State] = (), initial: str | None = None):
        doc    = inspect.getmodule(type(self)).__doc__ or ""
        states = list(states) or [State("on")]
        super().__init__(name, {s.name: s for s in states}, initial or states[0].name,
                         desc=self.DESC or " ".join(doc.split("\n\n")[0].split()), tags=self.TAGS)


class Step(Action):
    """An action in Python, of a program in code.

        program     its program, at hand in `apply`
        apply()     what it does, each step its own

    It isn't one of `Action.kinds`, so the config can't write one. It's shown by its name
    (`Remind`: "remind").
    """

    program: Ritual

    def __init_subclass__(cls, **kwargs: Any):
        super(Action, cls).__init_subclass__(**kwargs)  # past Action's: not a kind of the config

    def __init__(self, program: Ritual):
        self.program = program

    def __repr__(self) -> str:
        return snake(type(self).__name__)


Action.kinds.pop(snake(Step.__name__))  # nor is Step itself


def make_branch(goto: str, desc: str = "", **when: Callable[[], Any]) -> Branch:
    """A way out of a state.

        goto        the state it goes to
        desc        why it's taken, in a line
        **when      its conditions, by name: a function each, called as the way is tried

    It's taken when every condition is true now (none: always).
    """
    return Branch(goto, conds=[Check(name, test) for name, test in when.items()], desc=desc)


class Check:
    """A way out's condition in code.

        expr        what it's shown as: its name in `make_branch`
        test        the function it asks
        current()   what `test` says now
    """

    def __init__(self, expr: str, test: Callable[[], Any]):
        self.expr, self.test = expr, test

    def current(self) -> Any:
        return self.test()


def make_variable(name: str, value: Any = None) -> Variable:
    """Variable `name`, starting at `value`: the one there is, if there's one already."""
    found = Stream.registry.get(name)
    return found if isinstance(found, Variable) else Variable(name, value)


def find_variable(name: str) -> Variable:
    """Variable `name`. ConfigError if there's none."""
    found = Stream.registry.get(name)
    if not isinstance(found, Variable):  raise ConfigError(f"there's no variable {name}")
    return found


def popup_open() -> bool:
    """Whether a question waits for you."""
    return queued("usr") > 0


async def choose(context: str, options: list[tuple[str, str]], timeout: float = 24 * 3600, **show: Any) -> str | None:
    """A question whose options each mean something to the program.

        context     the question
        options     (label, what it means), in order
        timeout     seconds it waits for your answer
        **show      what's shown with it, as for `Popup.ask`

    What the option you picked means (None: no answer).
    """
    index = await Popup.ask(context, [label for label, _ in options], timeout, **show)
    return None if index is None else options[index][1]


# --- tables -------------------------------------------------------------------------------

Row = TypeVar("Row")


class Table(Generic[Row]):
    """A table of proki.db, a row for each `Row` (a dataclass), a column for each of its fields.

        NAME                    the table's name
        KEY                     the field it's keyed by ("id", an int: given as a row is added)

        create(row)             the row added, replacing the one with its key: its key
        read(key, **where)      the rows with `key`, and whose fields are as given (none: all),
                                by their key
        update(key, **fields)   some of a row's fields changed
        delete(key)             the row removed

    A text, a number or a yes/no is kept as it is, a time as UTC ISO text, an Enum as its
    value, anything else as JSON. The table is made if it's missing, and never changed if
    it's there. Each write is kept at once, or with the transaction it's part of.
    """

    NAME : ClassVar[str]
    KEY  : ClassVar[str] = "id"
    ROW  : ClassVar[type]

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        for base in getattr(cls, "__orig_bases__", ()):
            if typing.get_origin(base) is Table:  cls.ROW = typing.get_args(base)[0]

    def __init__(self, db: sqlite3.Connection):
        self.db    = db
        self.names = [f.name for f in fields(self.ROW)]
        self.kinds = {name: kind(hint) for name, hint in typing.get_type_hints(self.ROW).items()}
        self.db.execute(f"CREATE TABLE IF NOT EXISTS {self.NAME} ({', '.join(self.column(n) for n in self.names)})")

    def create(self, row: Row) -> Any:
        values = dict(zip(self.names, astuple(row)))
        if self.KEY == "id" and values["id"] is None:  del values["id"]  # given by the table
        cursor = self.write(f"INSERT OR REPLACE INTO {self.NAME} ({quoted(values)}) VALUES ({', '.join('?' * len(values))})",
                            [self.put(n, v) for n, v in values.items()])
        return values.get(self.KEY, cursor.lastrowid)

    def read(self, key: Any = None, /, **where: Any) -> list[Row]:
        if key is not None:  where[self.KEY] = key
        test   = " AND ".join(f"{quoted([n])} IS ?" for n in where) or "1"
        cursor = self.db.execute(f"SELECT {quoted(self.names)} FROM {self.NAME} WHERE {test} ORDER BY {quoted([self.KEY])}",
                                 [self.put(n, v) for n, v in where.items()])
        return [self.ROW(*(self.get(n, v) for n, v in zip(self.names, row))) for row in cursor]

    def update(self, key: Any, **changed: Any) -> None:
        if unknown := set(changed) - set(self.names) | ({self.KEY} & set(changed)):
            raise ValueError(f"{self.NAME} has no {', '.join(sorted(unknown))} to change")
        sets = ", ".join(f"{quoted([n])} = ?" for n in changed)
        self.write(f"UPDATE {self.NAME} SET {sets} WHERE {quoted([self.KEY])} = ?",
                   [*(self.put(n, v) for n, v in changed.items()), self.put(self.KEY, key)])

    def delete(self, key: Any) -> None:
        self.write(f"DELETE FROM {self.NAME} WHERE {quoted([self.KEY])} = ?", [self.put(self.KEY, key)])

    # --- columns ------------------------------------------------------------------------------

    def column(self, name: str) -> str:
        made, optional = self.kinds[name]
        sql = "INTEGER" if made in (int, bool) else "REAL" if made is float else "TEXT"
        if name == self.KEY:  return f"{quoted([name])} {sql} PRIMARY KEY"
        return f"{quoted([name])} {sql}" + ("" if optional else " NOT NULL")

    def put(self, name: str, value: Any) -> Any:
        """A field's value, as kept."""
        made, _ = self.kinds[name]
        if value is None or made in (str, int, float):  return value
        if made is bool:                                return int(value)
        if made is datetime:                            return value.astimezone(UTC).isoformat()
        if isinstance(made, type) and issubclass(made, Enum):  return value.value
        return json.dumps(value)

    def get(self, name: str, value: Any) -> Any:
        """A field's value, as kept, read back."""
        made, _ = self.kinds[name]
        if value is None or made in (str, int, float):  return value
        if made is bool:                                return bool(value)
        if made is datetime:                            return datetime.fromisoformat(value)
        if isinstance(made, type) and issubclass(made, Enum):  return made(value)
        return json.loads(value)

    def write(self, sql: str, args: list) -> sqlite3.Cursor:
        part = self.db.in_transaction
        cursor = self.db.execute(sql, args)
        if not part:  self.db.commit()
        return cursor


def kind(hint: Any) -> tuple[Any, bool]:
    """A field's type, and whether it can be None: `str | None` gives (str, True)."""
    if typing.get_origin(hint) in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(hint) if a is not type(None)]
        return (args[0] if len(args) == 1 else Any), len(args) < len(typing.get_args(hint))
    return hint, False


def quoted(names: Iterable[str]) -> str:
    """Column names, each quoted ("group" is a word of SQL)."""
    return ", ".join(f'"{n}"' for n in names)
