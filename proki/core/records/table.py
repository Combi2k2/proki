"""A kind of record, as a variable: its records in your order, and one of them.

    work.tasks = work.tasks + [{...}]   a record added (one left out: removed)
    work.task  = work.tasks[0]          that record, from now on
    me.estimate                         in a field's formula: the record's own field
    res.hours                           in an ask's formula: its answer
"""

from __future__ import annotations

import ast
import copy
import json
import re
import string
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, ClassVar

from proki.core.programs import Program
from proki.core.records.field import ASKS, KEPT, Asker, At, Field, Preface, Store
from proki.core.records.linked import Linked
from proki.core.signals import Expr, Stream, Variable
from proki.errors import ExprError, VariableError
from proki.types import Type, listof, oftype, schema, typename
from proki.utils import minutes, moment

STAMPS = {
    "id"         : "integer",
    "created_at" : "time",
    "updated_at" : "time"
}


def clock() -> datetime:
    """The time as the programs have it, else now."""
    return Program.now or datetime.now(UTC)


def reserved() -> set[str]:
    """The names the code keeps, never the config's: each variable it made, and its first name."""
    names = [name for name, made in Stream.registry.items() if isinstance(made, Linked | Records | Record)]
    return {*names, *(name.split(".")[0] for name in names)}


class Records(Variable):
    """A kind of record's records, in your order: each with its id, created_at and updated_at.

        name      what the config reads it as: work.tasks
        db        where its records are kept
        kind      which kind of record: task, group
        fields    the fields proki comes with
        tables    where your fields and contexts are kept
        context   what its questions are read under, until you change it
        desc      what it is
        code      the fields its code works out: {key: (type, what it is, how)}
    """

    writes: ClassVar[int] = 0   # every table's, so far: a record read again once one's written

    def __init__(self, name: str, db: Any, kind: str, fields: list[Field], tables: tuple[Store[Field], Store[Preface]],
                 context: str = "", desc: str = "", code: dict[str, tuple[Type, str, Callable[[Row], Any]]] | None = None):
        super().__init__(name, None, desc, type="array")
        self.db, self.sql, self.code  = db, f"records_{kind}", code or {}
        self.me, self.res, self.asker = Value(), Value(), Asker(self)
        self.defined, self.prefaces   = tables
        self.shipped, self.preface    = {f.key: f for f in fields}, context
        self.seen : tuple[Any, list[Row], dict[int, Row]] | None = None     # the records as read, by id too, and as of when
        db.execute(f"CREATE TABLE IF NOT EXISTS {self.sql} (id INTEGER PRIMARY KEY AUTOINCREMENT, position REAL NOT NULL, "
                   f"created_at REAL NOT NULL, updated_at REAL NOT NULL, kept TEXT NOT NULL, cache TEXT NOT NULL)")
        self.load()

    def load(self, new: Field | None = None) -> None:
        """Its fields as they're kept now, and `new` among them."""
        self.fields = self.shipped | {f.key: f for f in self.defined.read()} | ({new.key: new} if new else {})
        rowtype = STAMPS | {k: f.type for k, f in self.fields.items()} | {k: t for k, (t, _, _) in self.code.items()}
        rowtype = {"type": "object", "properties": {k: schema(t) for k, t in rowtype.items()}}
        self.me._typed  = rowtype
        self._typed     = listof(rowtype)
        self.streams, self.seen = {}, None

    def current(self) -> list[Row]:
        """Its records, in order, as they are now."""
        if self.seen is None or self.seen[0] != (Records.writes, Stream.now):
            rows      = [Row(self, *row) for row in self.db.execute(f"SELECT id, created_at, updated_at, kept, cache FROM {self.sql} ORDER BY position, id")]
            self.seen = (Records.writes, Stream.now), rows, {row["id"]: row for row in rows}
        return self.seen[1]

    def compile(self, expr: str) -> Stream:
        """A formula, as it's read for any of its records. ExprError for a name there isn't, or a field (me.nope)."""
        if expr not in self.streams:
            made, known = Expr(expr), self.me._typed["properties"]
            read = [n.attr for n in ast.walk(made.tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "me"]
            if nope := [key for key in read if key not in known]:
                raise ExprError(f"{expr!r}: {self.name} has no field {', '.join(nope)}")
            before = {name: Stream.registry.get(name) for name in ("me", "res")}
            Stream.registry.update({"me": self.me, "res": self.res})
            try:
                self.streams[expr] = made.stream()
            finally:
                for name, was in before.items():
                    if was is None:  del Stream.registry[name]
                    else:            Stream.registry[name] = was
        return self.streams[expr]

    @contextmanager
    def writing(self) -> Iterator[None]:
        """Its records written together, all or none.

            with tasks.writing():  ...
        """
        with self.db:
            yield
        Records.writes += 1

    def set(self, records: list | None, at: datetime | None = None) -> list[int]:
        """The table as `records`, in order (one without an id: added; one left out: removed). Their ids.

            at   when it changed (none: now)
        """
        if not isinstance(records, list):  raise VariableError(f"{self.name} is a list of records ({records!r})")
        with self.writing():
            ids = [self.put_row(record, position, at) for position, record in enumerate(records)]
            self.db.execute(f"DELETE FROM {self.sql} WHERE id NOT IN ({', '.join('?' * len(ids))})", ids)
        return ids

    def reset(self) -> None:
        pass  # kept in its table, not by a program

    def get_row(self, id: Any) -> Row | None:
        """A record by its id, as it is now (none: None)."""
        self.current()
        return self.seen[2].get(id)

    def add_row(self, record: dict) -> int:
        """A record kept (no id: added, last). Its id. VariableError for a value not of its type."""
        with self.writing():
            return self.put_row(record)

    def put_row(self, record: dict, position: int | None = None, at: datetime | None = None) -> int:
        """A record kept, new or over the one with its id. Its id. VariableError for a field it hasn't, or a value not of its type.

            position   where it goes (none: last if it's new, else where it was)
            at         when it changed (none: now)
        """
        if nope := sorted(set(record) - set(self.fields) - set(STAMPS)):
            raise VariableError(f"{self.name} has no field {', '.join(nope)}")
        kept = {k: dict.get(record, k) for k, f in self.fields.items() if f.kept}
        if bad := next((k for k, v in kept.items() if not oftype(v, self.fields[k].type)), None):
            raise VariableError(f"{self.name}.{bad} is of type {typename(self.fields[bad].type)} ({kept[bad]!r})")

        before, now, saved = self.get_row(dict.get(record, "id")), minutes(at or clock()), json.dumps(kept)
        if before is None:
            last = f"(SELECT coalesce(max(position) + 1, 0) FROM {self.sql})"   # a new one goes last, unless placed
            return self.db.execute(f"INSERT INTO {self.sql} (position, created_at, updated_at, kept, cache) VALUES (coalesce(?, {last}), ?, ?, ?, '{{}}')",
                                   (position, now, now, saved)).lastrowid
        changed = any(dict.get(before, k) != v for k, v in kept.items())       # moving it alone isn't an update
        self.db.execute(f"UPDATE {self.sql} SET position = coalesce(?, position), kept = ?, updated_at = ? WHERE id = ?",
                        (position, saved, now if changed else before["updated_at"], before["id"]))
        return before["id"]

    def validate(self, text: str) -> None:
        """ExprError for a name `text` reads that there isn't: {me.name}, {work.plan}."""
        for _, expr, _, _ in string.Formatter().parse(text):
            if expr:  self.compile(expr)

    def evaluate(self, row: Row, expr: str, res: Any = None) -> tuple[Any, Any]:
        """A formula's value for a record, and its type (a name there isn't: None, any).

            res   what it reads as `res`: an ask's answer
        """
        def anew(formula: Stream) -> Stream:  # worked out again for this record: a stream read by name keeps this cycle's value
            if not (formula.name and Stream.registry.get(formula.name) is formula):
                formula._cached = False
                for i in formula.inputs:  anew(i)
            return formula

        try:        stream = self.compile(expr)
        except:     return None, "any"
        before, (self.me.value, self.res.value) = (self.me.value, self.res.value), (row, res)
        try:        return anew(stream).current(), stream.type
        finally:    self.me.value, self.res.value = before

    def render(self, row: Row, text: str) -> str:
        """`text` for a record, each {expr} filled in (a time: its day; a list: its items). A line with an empty one left out."""
        lines = []
        for line in text.splitlines():
            said = []
            for literal, expr, spec, _ in string.Formatter().parse(line):
                value, type = self.evaluate(row, expr) if expr else ("", None)
                value = ("" if value is None else f"{moment(value):%a %d %b}" if type == "time"
                         else "; ".join(map(str, value)) if isinstance(value, list) else value)
                if expr and value == "":  break
                said.append(literal + format(value, spec or ""))
            else:
                lines.append("".join(said))
        return "\n".join(lines)

    def run(self, row: Row, f: Field) -> Any:
        """A field's value for a record: its first source with one."""
        for s in f.srcs:
            if s["from"] in KEPT:         found = s.get("initial") if (kept := dict.get(row, f.key)) is None else kept   # none set: where a new one starts
            elif s["from"] == "expr":     found = self.evaluate(row, s["expr"])[0]
            elif (found := self.ask(row, f, s)) is not None and s.get("expr"):
                found = self.evaluate(row, s["expr"], found)[0]
            if found is not None:  return found

    def ask(self, row: Row, f: Field, s: dict) -> Any:
        """An ask's last answer for a record (none yet: None): asked again once what it asks changes."""
        channel = s["from"]

        def word() -> dict:  # what it'd ask now, as it reads for this record: asked again once it changes
            asked = {
                "channel" : channel,
                "about"   : self.render(row, self.context(channel)),                 # the preface
                "said"    : self.render(row, s.get("question") or s["context"]),     # the question
            }
            if channel == "jev":  asked |= {k: s[k] for k in ("type", "criteria") if k in s}
            if channel == "llm":  asked["schema"] = schema(s.get("schema", f.type))   # what it answers in
            return asked

        self.asker.ask(at := (row["id"], f.key, channel), word, s.get("timeout"))
        return (self.read(at) or {}).get("answer")

    def read(self, at: At) -> dict | None:
        """An ask's last question and its answer (none yet: None)."""
        return row.cache.get(at[1], {}).get(at[2]) if (row := self.get_row(at[0])) else None

    def keep(self, at: At, kept: dict | None) -> None:
        """An ask's last question and its answer kept (None: forgotten)."""
        id, key, channel = at
        if (row := self.get_row(id)) is not None:
            mine = {s: v for s, v in row.cache.get(key, {}).items() if s != channel} | ({channel: kept} if kept is not None else {})
            with self.writing():
                self.db.execute(f"UPDATE {self.sql} SET cache = ? WHERE id = ?", (json.dumps(row.cache | {key: mine}), id))

    def pop(self, at: At) -> None:
        """An ask's answer forgotten: asked again the next time it's read."""
        self.keep(at, None)

    def define(self, f: Field) -> None:
        """A field of yours, new or changed. ExprError for a name there isn't; ValueError for one its code keeps."""
        if f.key in STAMPS or f.key in self.code:  raise ValueError(f"{self.name}.{f.key} is kept by its code")
        self.load(f)
        try:
            for s in f.srcs:
                if s.get("question"):   self.validate(s["question"])
                if s.get("context"):    self.validate(s["context"])
                if s.get("expr"):       self.compile(s["expr"])
            self.defined.create(f)
        finally:
            self.load()

    def remove(self, key: str) -> None:
        """A field of yours gone: back as proki has it, if it came with one."""
        self.defined.delete(key)
        self.load()

    def rename(self, key: str, to: str) -> None:
        """A field of yours named `to`: its values with it, and every formula that reads it changed to match."""
        if key in self.shipped:     raise ValueError(f"{key} came with proki: it can't be renamed")
        if to in self.fields:       raise ValueError(f"there's a field {to} already")
        if to in self.code:         raise ValueError(f"there's a field {to} already")
        if to in STAMPS:            raise ValueError(f"there's a field {to} already")
        Field(to)  # ValueError: not a name it can have
        reworded = lambda text: re.sub(rf"\bme\.{re.escape(key)}\b", f"me.{to}", text)
        moved    = lambda kept: json.dumps({to if k == key else k: v for k, v in json.loads(kept).items()})
        for f in self.defined.read():
            srcs = [{k: reworded(v) if k in ("expr", "question", "context") else v for k, v in s.items()} for s in f.srcs]
            self.defined.delete(f.key)
            self.defined.create(Field(to if f.key == key else f.key, f.desc, srcs, f.type))
        for preface in self.prefaces.read():
            self.prefaces.create(Preface(preface.channel, reworded(preface.text)))
        with self.writing():
            rows = self.db.execute(f"SELECT id, kept, cache FROM {self.sql}").fetchall()
            self.db.executemany(f"UPDATE {self.sql} SET kept = ?, cache = ? WHERE id = ?", [(moved(kept), moved(cache), id) for id, kept, cache in rows])
        self.load()

    def rerun(self, key: str, source: str | None = None, id: Any = None) -> None:
        """A field asked again.

            source   the ask (none: each)
            id       the record (none: every one)
        """
        rows = [self.get_row(id)] if id is not None else self.current()
        for at in [(row["id"], key, s) for row in rows for s in ((source,) if source else ASKS)]:
            self.pop(at)

    def context(self, channel: str) -> str:
        """What `channel`'s questions are read under, for every record."""
        return found[0].text if (found := self.prefaces.read(channel)) else self.preface

    def reword(self, channel: str, text: str) -> None:
        """`channel`'s context changed (empty: back as it came). ExprError for a name there isn't."""
        if channel not in ASKS:  raise ValueError(f"no channel {channel!r}: jev or llm")
        self.validate(text)
        if text.strip():  self.prefaces.create(Preface(channel, text))
        else:             self.prefaces.delete(channel)


class Record(Variable):
    """One of a table's records, as it is now (none: None), and that one from now on.

        work.task = work.tasks[0]
        work.task.name
    """

    def __init__(self, name: str, table: Records, desc: str = ""):
        super().__init__(name, None, desc, persist=True, type="integer")   # kept as its id
        self.table, self._typed = table, table.type["items"]                # read as its record

    def _keep(self, id: int | None) -> None:
        self.value = id
        if Variable.store is not None:
            Variable.store.save(self.name, id, "integer")

    def current(self) -> Row | None:
        return self.table.get_row(self.value)

    def set(self, record: dict | None) -> None:
        if record is not None and not isinstance(record, dict):
            raise VariableError(f"{self.name} is one of {self.table.name} ({record!r})")
        self._keep(None if record is None else self.table.add_row(record))

    def reset(self) -> None:
        pass  # kept, not started over by a program


class Row(dict):
    """A record as it reads now: its fields by key, the ones you set settable.

        row["estimate"] = 30
        row.save()
    """

    def __init__(self, table: Records, id: int, created_at: float, updated_at: float, kept: str, cache: str):
        super().__init__(json.loads(kept) | {"id": id, "created_at": created_at, "updated_at": updated_at})
        self.table, self.cache, self.worked = table, json.loads(cache), {}

    def __getitem__(self, key: str) -> Any:
        if key not in self.table.fields and key not in self.table.code:  return super().__getitem__(key)
        if key not in self.worked:
            self.worked[key] = None  # one that reads itself: None
            self.worked[key] = self.table.code[key][2](self) if key in self.table.code else self.table.run(self, self.table.fields[key])
        return self.worked[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self.table.code or key in self.table.fields and not self.table.fields[key].kept:
            raise VariableError(f"{self.table.name}.{key} is worked out: it isn't set")
        super().__setitem__(key, value)
        self.worked.clear()

    def get(self, key: str, default: Any = None) -> Any:
        return self[key] if key in self.table.fields or key in self.table.code or key in self else default

    def save(self) -> None:
        """Kept in its table, as it is now."""
        self.table.add_row(self)

    def __deepcopy__(self, memo: dict) -> Row:
        made = dict.__new__(Row)
        dict.update(made, copy.deepcopy(dict(self), memo))
        made.table, made.cache, made.worked = self.table, self.cache, {}
        return made


class Value(Stream):
    """What a formula reads as `me` or `res`, as it's read."""

    value: Any = None

    def current(self) -> Any:
        return self.value
