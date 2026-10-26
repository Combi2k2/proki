"""Where proki keeps what it keeps: a class each, over one database.

    db = connect(path)
    StateDB(db)         values by key: proki's own, not a program's
    SwitchDB(db)        the programs switched off
    VariableDB(db)      each variable's latest value
    HistoryDB(db)       each persisted signal's values over time
    SpecDB(db)          your programs, as specs
    Table[Row]          a kind of row (a dataclass), kept a row each

A row, as a tool takes it and gives it:

    hinted(hint)        a field's type, and whether it can be None
    schema(row)         a dataclass's fields as JSON schemas, by name
    needed(row)         the fields a new row needs
    typed(row, args)    a tool's arguments, as the fields are
    plain(row)          a row, as a tool gives it
"""

from __future__ import annotations

import json
import re
import sqlite3
import types
import typing
from collections.abc import Iterable, Iterator
from dataclasses import MISSING, asdict, astuple, fields
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any, ClassVar, Generic, TypeVar

from proki.core.records import Field, Preface
from proki.model import Spec, Specs
from proki.model.model import Model
from proki.types import Type, schema as type_schema
from proki.utils import joined

SCHEMA = """
CREATE TABLE IF NOT EXISTS state (
    key         TEXT PRIMARY KEY,   -- "programs_off"
    value       TEXT NOT NULL       -- JSON
);
CREATE TABLE IF NOT EXISTS variables (
    name        TEXT PRIMARY KEY,   -- a variable of the config
    value       TEXT NOT NULL,      -- its latest value, as JSON
    updated_at  TEXT NOT NULL       -- when it last changed (UTC)
);
CREATE TABLE IF NOT EXISTS signal_history (
    name        TEXT NOT NULL,      -- a persisted signal
    t           TEXT NOT NULL,      -- UTC, ISO
    value       TEXT,               -- JSON
    PRIMARY KEY (name, t)
);
"""


def connect(path) -> sqlite3.Connection:
    """The database at `path`, made if it's missing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    return db


class StateDB:
    """Values by key.

        state.set("seen", 3)
        state.get("seen", 0)
    """

    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def get(self, key: str, default: Any = None) -> Any:
        """The value at `key` (none: `default`)."""
        row = self.db.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key: str, value: Any) -> None:
        """`value` kept at `key`: at once, or with the transaction it's part of."""
        write(self.db, "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)", (key, json.dumps(value)))


class SwitchDB:
    """The programs switched off, by name."""

    KEY = "programs_off"

    def __init__(self, db: sqlite3.Connection):
        self.kv = StateDB(db)

    def load(self) -> set[str]:
        """The names switched off."""
        return set(self.kv.get(self.KEY, []))

    def save(self, off: set[str]) -> None:
        """`off` switched off, the rest on."""
        self.kv.set(self.KEY, sorted(off))


class VariableDB:
    """Each variable's latest value, by its name: each list of objects in it, at any depth, kept a row an item."""

    def __init__(self, db: sqlite3.Connection):
        self.db, self.tables = db, set()   # the tables made

    def load(self, name: str, type: Type | None = None) -> Any:
        """Its value as last saved, as `type` says. KeyError if it was never saved."""
        row = self.db.execute("SELECT value FROM variables WHERE name = ?", (name,)).fetchone()
        if row is None:  raise KeyError(name)
        tables, rows = set(list_paths(type)), {}
        for path in tables:
            self.made(name, path)
            listed = self.db.execute(f'SELECT id, parent, extra FROM "{list_table(name, path)}" ORDER BY parent, position')
            for id, parent, extra in listed:
                rows.setdefault((path, parent), []).append((id, json.loads(extra)))
        def filled(value: Any, at: str, parent: int | None) -> Any:
            if at in tables and value == []:  return [filled(item, at, id) for id, item in rows.get((at, parent), [])]
            if isinstance(value, dict):       return {k: filled(v, joined(at, k), parent) for k, v in value.items()}
            return value
        return filled(json.loads(row[0]), "", None)

    def save(self, name: str, value: Any, type: Type | None = None) -> None:
        """`value` kept as its latest, as `type` says."""
        tables = set(list_paths(type))
        rows   = {path: [] for path in tables}
        def split(value: Any, at: str, parent: int | None) -> Any:
            if at in tables and isinstance(value, list):
                for position, item in enumerate(value):
                    rows[at].append([id := len(rows[at]) + 1, parent, position, None])
                    rows[at][-1][3] = json.dumps(split(item, at, id))
                return []
            if isinstance(value, dict):  return {k: split(v, joined(at, k), parent) for k, v in value.items()}
            return value
        kept = split(value, "", None)
        with self.db:
            for path, made in rows.items():
                self.made(name, path)
                self.db.execute(f'DELETE FROM "{list_table(name, path)}"')
                self.db.executemany(f'INSERT INTO "{list_table(name, path)}" (id, parent, position, extra) VALUES (?, ?, ?, ?)',
                                    made)
            self.db.execute("INSERT OR REPLACE INTO variables (name, value, updated_at) VALUES (?, ?, ?)",
                            (name, json.dumps(kept), datetime.now(UTC).isoformat()))

    def made(self, name: str, path: str) -> None:
        """The table for one of its lists, made if it's missing."""
        if (made := list_table(name, path)) in self.tables:  return
        self.db.execute(f'CREATE TABLE IF NOT EXISTS "{made}" '
                        f'(id INTEGER PRIMARY KEY, parent INTEGER, position INTEGER NOT NULL, extra TEXT NOT NULL)')
        self.tables.add(made)


class HistoryDB:
    """Each persisted signal's values over time."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def load(self, name: str, since: datetime) -> list[tuple[datetime, Any]]:
        """Its values after `since`, in order."""
        rows = self.db.execute("SELECT t, value FROM signal_history WHERE name = ? AND t > ? ORDER BY t",
                               (name, since.astimezone(UTC).isoformat()))
        return [(datetime.fromisoformat(t), json.loads(v)) for t, v in rows]

    def save(self, name: str, t: datetime, value: Any) -> None:
        """Its value at `t`."""
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO signal_history (name, t, value) VALUES (?, ?, ?)",
                            (name, t.astimezone(UTC).isoformat(), json.dumps(value)))

    def forget(self, name: str, before: datetime) -> None:
        """Its values at or before `before` forgotten, but the last: what it was then."""
        cut = before.astimezone(UTC).isoformat()
        with self.db:
            self.db.execute("DELETE FROM signal_history WHERE name = ? AND t <= ? AND t < "
                            "(SELECT MAX(t) FROM signal_history WHERE name = ? AND t <= ?)", (name, cut, name, cut))


class SpecDB:
    """Your programs, as specs.

        save(specs)     all of them, in place of the last (one that fails: the last kept)
        load()          as last saved (none yet: None)
    """

    CYCLE = "programs_cycle"

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.kv = StateDB(db)

    def load(self) -> Specs | None:
        if not self.db.execute("SELECT 1 FROM sqlite_master WHERE name = 'spec_programs'").fetchone():
            return None
        specs = Specs(self.kv.get(self.CYCLE, 10))
        for kind, cls in Spec.kinds.items():
            cursor  = self.db.execute(f"SELECT * FROM {self.table(kind)} ORDER BY position")
            columns = [c[0] for c in cursor.description][1:]  # after the position
            hints   = typing.get_type_hints(cls)
            for row in cursor:
                data = {name: value if self.plain(hints[name]) else json.loads(value)
                        for name, value in zip(columns, row[1:])}
                getattr(specs, Model.LISTS[kind]).append(cls.parse(data))
        return specs

    def save(self, specs: Specs) -> None:
        with self.db:
            self.db.execute("BEGIN")  # the tables are dropped and made in it too
            self.kv.set(self.CYCLE, specs.cycle)
            for kind, cls in Spec.kinds.items():
                table, hints = self.table(kind), typing.get_type_hints(cls)
                names = [f.name for f in fields(cls)]
                self.db.execute(f"DROP TABLE IF EXISTS {table}")
                self.db.execute(f"CREATE TABLE {table} (position INTEGER PRIMARY KEY, {quoted(names)})")
                self.db.executemany(
                    f"INSERT INTO {table} VALUES (?, {', '.join('?' for _ in names)})",
                    [(i, *(v if self.plain(hints[n]) else json.dumps(v) for n in names for v in [getattr(spec, n)]))
                     for i, spec in enumerate(getattr(specs, Model.LISTS[kind]))])

    @staticmethod
    def table(kind: str) -> str:
        """Where a kind of spec is kept."""
        return f"spec_{Model.LISTS[kind]}"

    @staticmethod
    def plain(hint: Any) -> bool:
        """Whether a field is kept as it is (a text, a word of a few, or none), not as JSON."""
        if typing.get_origin(hint) is typing.Literal:
            return all(isinstance(a, str) for a in typing.get_args(hint))
        return hint is str or hint == str | None


# --- tables -------------------------------------------------------------------------------

Row = TypeVar("Row")


class Table(Generic[Row]):
    """A kind of row (a dataclass), kept a row each, by its key.

        class Notes(Table[Note]):  NAME = "notes"
        notes = Notes(db)

        NAME                    its name
        KEY                     the field it's keyed by (id: given as a row's added)
        create(row)             the row added, in place of the one with its key: its key
        read(key, **where)      the rows with `key`, their fields as given (none: all), by key
        update(key, **fields)   some of a row's fields changed
        delete(key)             the row gone
    """

    NAME   : ClassVar[str]
    KEY    : ClassVar[str] = "id"
    ROW    : ClassVar[type]
    writes : ClassVar[int] = 0   # every table's writes so far: what's read of them is as it was, until the next

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        for base in getattr(cls, "__orig_bases__", ()):
            if typing.get_origin(base) is Table:  cls.ROW = typing.get_args(base)[0]

    def __init__(self, db: sqlite3.Connection):
        self.db    = db
        self.names = [f.name for f in fields(self.ROW)]
        self.kinds = {name: hinted(hint) for name, hint in typing.get_type_hints(self.ROW).items()}
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

    def update(self, key: Any, /, **changed: Any) -> None:
        if unknown := set(changed) - set(self.names) | ({self.KEY} & set(changed)):
            raise ValueError(f"{self.NAME} has no {', '.join(sorted(unknown))} to change")
        sets = ", ".join(f"{quoted([n])} = ?" for n in changed)
        self.write(f"UPDATE {self.NAME} SET {sets} WHERE {quoted([self.KEY])} = ?",
                   [*(self.put(n, v) for n, v in changed.items()), self.put(self.KEY, key)])

    def delete(self, key: Any) -> None:
        self.write(f"DELETE FROM {self.NAME} WHERE {quoted([self.KEY])} = ?", [self.put(self.KEY, key)])

    # --- columns ------------------------------------------------------------------------------

    def column(self, name: str) -> str:
        """A field's column, as it's made."""
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
        """Written, and counted."""
        Table.writes += 1
        return write(self.db, sql, args)


# --- helpers ------------------------------------------------------------------------------

def list_paths(type: Type | None) -> list[str]:
    """Each list of objects a value of `type` has, by its path: "" (itself), tasks, tasks.steps."""
    def found(made: dict, at: str) -> Iterator[str]:
        items = made.get("items") if made.get("type") == "array" else None
        if isinstance(items, dict) and items.get("type") == "object":
            yield at
            made = items
        for key, part in made.get("properties", {}).items() if made.get("type") == "object" else ():
            yield from found(part, joined(at, key))
    return list(found(type_schema(type), ""))


def list_table(name: str, path: str) -> str:
    """The table a variable's list of objects is kept in, by its path: work.plan's changes."""
    return "var_" + re.sub(r"\W", "_", joined(name, path))


def record_tables(db: sqlite3.Connection, kind: str) -> tuple[Table[Field], Table[Preface]]:
    """A kind of record's fields of yours, and its contexts: Records("work.tasks", db, "task", ..., record_tables(db, "task"))."""
    class Fields(Table[Field]):         NAME, KEY = f"{kind}_fields", "key"
    class Contexts(Table[Preface]):     NAME, KEY = f"{kind}_context", "channel"
    return Fields(db), Contexts(db)


def write(db: sqlite3.Connection, sql: str, args: Iterable[Any]) -> sqlite3.Cursor:
    """`sql` run, and kept: at once, or with the transaction it's part of."""
    part   = db.in_transaction
    cursor = db.execute(sql, args)
    if not part:  db.commit()
    return cursor


def quoted(names: Iterable[str]) -> str:
    """Column names, each quoted ("group" is a word of SQL)."""
    return ", ".join(f'"{n}"' for n in names)


# --- a row (a dataclass), as JSON -------------------------------------------------------------

SCHEMAS = {
    str      : {"type": "string"},
    int      : {"type": "integer"},
    float    : {"type": "number"},
    bool     : {"type": "boolean"},
    datetime : {"type": "string", "format": "date-time"}
}


def hinted(hint: Any) -> tuple[Any, bool]:
    """A field's type, and whether it can be None: `str | None` gives (str, True)."""
    if typing.get_origin(hint) in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(hint) if a is not type(None)]
        return (args[0] if len(args) == 1 else Any), len(args) < len(typing.get_args(hint))
    return hint, False


def schema(row: type, without: Iterable[str] = ()) -> dict:
    """A dataclass's fields as JSON schemas, by name: a time as ISO text, a list as its items',
    one that can be None as null too."""
    names, shapes = {f.name for f in fields(row)} - set(without), {}
    for name, hint in typing.get_type_hints(row).items():
        if name not in names:  continue
        made, optional = hinted(hint)
        if typing.get_origin(made) is list:  shape = {"type": "array", "items": SCHEMAS.get(typing.get_args(made)[0], {})}
        else:                                shape = dict(SCHEMAS.get(made, {}))
        if optional and "type" in shape:     shape["type"] = [shape["type"], "null"]
        shapes[name] = shape
    return shapes


def needed(row: type, without: Iterable[str] = ()) -> tuple[str, ...]:
    """A dataclass's fields with no default: the ones a new row needs."""
    return tuple(f.name for f in fields(row)
                 if f.name not in without and f.default is MISSING and f.default_factory is MISSING)


def typed(row: type, args: dict) -> dict:
    """Arguments as JSON gives them, as `row`'s fields are: a time from its ISO text."""
    times = {name for name, hint in typing.get_type_hints(row).items() if hinted(hint)[0] is datetime}
    return {name: datetime.fromisoformat(value) if name in times and isinstance(value, str) else value
            for name, value in args.items()}


def plain(row: Any) -> dict:
    """A row as JSON: its dates and times as ISO text."""
    return {name: value.isoformat() if isinstance(value, date) else value for name, value in asdict(row).items()}
