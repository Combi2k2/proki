"""Kinds of record (work.tasks, work.groups), as tools: a kind's records read, and one added,
changed, removed or moved, by the kind's name and the record's id. Times are ISO text.

    read("work.tasks")                          its records, in your order
    add("work.tasks", at, group=3, name=...)    a new one, last: its id
    change("work.tasks", 7, at, name=...)       some of its fields
    remove("work.groups", 7)                    and what's its (a group's tasks)
    move("work.tasks", 7, at, before=9)         before record 9 (None: last)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from proki.core.records import STAMPS, Records
from proki.core.records.table import Row
from proki.core.signals import Stream
from proki.tools.base import Tool
from proki.types import schema
from proki.utils import minutes, moment

NAME   = {"type": "string", "description": "the kind's name: work.tasks, work.groups"}
ID     = {"type": "integer"}
FIELDS = {"type": "object", "description": "its fields, by key (read_records: each one's type)"}


def kinds() -> list[str]:
    """The kinds of record there are, by name."""
    return [name for name, made in Stream.registry.items() if isinstance(made, Records)]


def table(name: str) -> Records:
    """The kind of record `name`. ValueError for one there isn't."""
    if not isinstance(found := Stream.registry.get(name), Records):
        raise ValueError(f"no record {name!r} ({', '.join(kinds()) or 'none made yet'})")
    return found


def shown(row: Row) -> dict:
    """A record as it's kept: each field set (none: where a new one starts), times as ISO text."""
    fields = row.table.fields
    types  = STAMPS | {k: f.type for k, f in fields.items()}
    made   = {k: dict.get(row, k) for k in STAMPS} | {k: next((s.get("initial") for s in f.srcs if s["from"] == "auto"), None) if (v := dict.get(row, k)) is None else v
                                                    for k, f in fields.items() if f.kept}
    return {k: moment(v).isoformat() if v is not None and types[k] == "time" else v for k, v in made.items()}


def read(name: str) -> list[dict]:
    """A kind's records, in your order."""
    return [shown(row) for row in table(name).current()]


def add(name: str, at: datetime | None = None, /, **fields: Any) -> int:
    """A new record of `name`, last, with `fields`, made `at` (None: now): its id."""
    with (made := table(name)).writing():
        return made.put_row(given(made, fields), at=at)


def change(name: str, id: int, at: datetime | None = None, /, **fields: Any) -> None:
    """Record `id` of `name`, with `fields`, changed `at` (None: now)."""
    row = found(made := table(name), id)
    with made.writing():
        made.put_row(row | given(made, fields), at=at)


def remove(name: str, id: int, /) -> None:
    """Record `id` of `name` deleted, and what's its (a group's tasks)."""
    found(made := table(name), id)
    made.set([row for row in made.current() if row["id"] != id])


def move(name: str, id: int, at: datetime | None = None, /, before: int | None = None) -> None:
    """Record `id` of `name` put before record `before` (None: last)."""
    moved = found(made := table(name), id)
    rest  = [row for row in made.current() if row["id"] != id]
    place = next((i for i, row in enumerate(rest) if row["id"] == before), len(rest))
    made.set([*rest[:place], moved, *rest[place:]], at)


def given(made: Records, fields: dict) -> dict:
    """Fields as a record keeps them: a time (or its ISO text) as minutes since 1970."""
    timed = {k for k, f in made.fields.items() if f.type == "time"}
    return {k: minutes(v) if isinstance(v, datetime) else minutes(datetime.fromisoformat(v)) if isinstance(v, str) and k in timed else v
            for k, v in fields.items()}


def found(made: Records, id: int) -> Row:
    if (row := made.get_row(id)) is None:
        raise ValueError(f"{made.name} has no record {id}")
    return row


def tools() -> list[Tool]:
    """Reading a kind of record, and adding, changing, removing and moving one."""
    now = lambda: datetime.now(UTC)
    return [
        Tool("read_records", "A kind of record's records, in your order, and its fields: what each is, and its type.",
             {"name": NAME}, lambda args: {"records": read(args["name"]),
                                           "fields" : {k: {"desc": f.desc, "type": schema(f.type)} for k, f in table(args["name"]).fields.items() if f.kept}},
             ("name",), readonly=True),
        Tool("add_record", "A new record, last: its fields, the ones it needs at least (a task: its group and name). Its id.",
             {"name": NAME, "fields": FIELDS}, lambda args: {"id": add(args["name"], now(), **args["fields"])}, ("name", "fields")),
        Tool("change_record", "Some of a record's fields. A `status` of open, done, or dropped (set aside, kept).",
             {"name": NAME, "id": ID, "fields": FIELDS}, lambda args: change(args["name"], args["id"], now(), **args["fields"]), ("name", "id", "fields")),
        Tool("remove_record", "A record deleted, and what's its (a group's tasks). To set it aside instead, change its status to dropped.",
             {"name": NAME, "id": ID}, lambda args: remove(args["name"], args["id"]), ("name", "id"), undoable=True),
        Tool("move_record", "A record before another (`before`, its id; none: last).",
             {"name": NAME, "id": ID, "before": {"anyOf": [{"type": "integer"}, {"type": "null"}]}},
             lambda args: move(args["name"], args["id"], now(), args.get("before")), ("name", "id")),
    ]
