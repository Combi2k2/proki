"""Your work: a board of groups of tasks, and the plan for the group at hand, as variables.

    work            all of it, one object: work.groups, work.group, work.tasks, work.task, work.plan
    work.groups     every group, in your order: work.groups[0].name
    work.group      the group at hand (None: none), one of work.groups
    work.tasks      every task, in your order: work.tasks.status
    work.task       the task at hand (None: none): work.tasks[argmax(work.tasks.start)]
    work.plan       what's planned for the group at hand, and its changes

A group (TaskGr) is a project, or what an errand takes. A task is one thing to do in a sitting,
by its key in its group: its name slugified as it's added, yours to change. A change suggested
(TaskOp) adds a task, or changes or removes one by its key, for you to accept or not.

Each field says what it is, and where a new one starts. A field of yours is added to them, or
is one of theirs said again, in the type it has. A group removed takes its tasks with it, and
a task its changes suggested.

A group's tags say what part of your life it's for, the most likely first, three at most. Each
is part of a row of the board, and the first one's row is where the group's card is.

A task's deadline is its own, or else its group's. It's ready once it's open, in an open group,
and the tasks it needs first are done or dropped. How it's weighed (`score`, `start`, `remind`)
is an expr each, for you to change.
"""

from __future__ import annotations

import itertools
import json
import sqlite3
import typing
from collections.abc import Callable
from dataclasses import MISSING, dataclass, field, fields, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from proki import settings
from proki.core.records import Field, Linked, Record, Records
from proki.core.records.table import Row
from proki.core.signals import Stream
from proki.errors import VariableError
from proki.storage import StateDB, Table, hinted, needed, record_tables, schema
from proki.tools.base import Tool
from proki.types import Type, typename
from proki.types import schema as shaped
from proki.utils import slugify

ROWS     = json.loads((settings.ASSETS_DIR / "tags.json").read_text())               # each row, and its tags
ROW      = {tag: row for row, tags in reversed(ROWS.items()) for tag in tags}        # each tag's row: the first it's in
TAGS     = list(dict.fromkeys(tag for tags in ROWS.values() for tag in tags))        # each tag, once
SHIPPED  = json.loads(Path(__file__).with_name("work.json").read_text())             # the fields proki comes with, as exprs
TEXTS    = {"type": "array", "items": {"type": "string"}}
TAGGED   = {"type": "array", "items": {"type": "string", "enum": TAGS}, "maxItems": 3, "uniqueItems": True}   # known tags
DEADLINE = [{"from": "user"}, {"from": "expr", "expr": "work.groups[index(work.groups.id, me.group)].deadline"}]  # its own, else its group's
CONTEXT  = "\n".join([   # what a task's questions are read under
    "A task: {me.name}",
    "{me.desc}",
    "Done when: {me.done_when}",
    "About {me.estimate} min",
    "Due {me.deadline}",
    "It's part of “{me.group_name}”",
    "{me.group_desc}",
])


# --- the board's fields -----------------------------------------------------------------------

def said(desc: str, default: Any = MISSING, type: Type | None = None, srcs: list[dict] | None = None) -> Any:
    """A field of the board's: what it is, where a new one starts (none: it's needed), and
    its type or sources where its hint doesn't say."""
    meta = {"desc": desc, "type": type, "srcs": srcs}
    if isinstance(default, list):
        return field(default_factory=list, metadata=meta)
    return field(default=default, metadata=meta)


@dataclass
class TaskGr:
    name       : str             = said("its name")
    desc       : str             = said("what it's for, and where it stands", "")
    tags       : list[str]       = said("what part of your life it's for, the most likely first: three at most", [], TAGGED)
    questions  : list[str]       = said("what only you can answer yet", [])
    estimate   : float | None    = said("how long all of it takes, in minutes (none: not said)", None)
    deadline   : datetime | None = said("when it's due (minutes since 1970)", None)
    status     : str             = said("open, done or dropped", "open")


@dataclass
class Task:
    group      : int             = said("its group's id")
    name       : str             = said("its name")
    desc       : str             = said("what it is", "")
    key        : str             = said("its key in its group: its name slugified as it's added, yours to change", "")
    done_when  : list[str]       = said("what done looks like: checks anyone could make", [])
    after      : list[int]       = said("the tasks it needs done first, by their ids", [])
    checkpoint : bool            = said("whether it's a short check that it all works together, and of what's next", False)
    note       : str             = said("your notes on it", "")
    estimate   : float           = said("how long it takes, in minutes", 25)
    deadline   : datetime | None = said("when it's due: its own, else its group's (minutes since 1970)", None, srcs=DEADLINE)
    status     : str             = said("open, done or dropped", "open")


OPS       = ("add", "change", "remove")
OP_FIELDS = [f.name for f in fields(Task) if f.name not in ("group", "after", "status")]   # a task's, an op gives


@dataclass
class TaskOp:
    id         : int | None
    group      : int | None                                      # None: a new group's, not made yet
    op         : str                                             # "add", "change" or "remove"
    task       : str | None       = None                         # change, remove: the task's key
    fields     : dict             = field(default_factory=dict)  # the task's fields it gives (add: its key too)
    after      : list[str] | None = None                         # the tasks it needs done first, by their keys

    def __post_init__(self):
        """An op there is: an add with a name, a change or a removal of a task, and a task's fields."""
        if self.op not in OPS:                                  raise ValueError(f"no op {self.op!r}")
        if self.op == "add" and not self.fields.get("name"):    raise ValueError("an add needs a name")
        if self.op != "add" and self.task is None:              raise ValueError(f"a {self.op} needs a task")
        if unknown := set(self.fields) - set(OP_FIELDS):        raise ValueError(f"no field {', '.join(sorted(unknown))} to give")


class TaskOpDB(Table[TaskOp]):
    NAME = "task_ops"

    def update(self, key: Any, /, **changed: Any) -> None:
        """Some of an op's fields, checked as an op's first (a field it hasn't: the table says so)."""
        [op] = self.read(key)
        replace(op, **{name: value for name, value in changed.items() if hasattr(op, name)})
        super().update(key, **changed)


# --- the board --------------------------------------------------------------------------------

class Kept(Records):
    """The board's groups or tasks: `row`'s fields, yours to set, then `more`. A new one needs
    the fields `row` has no default for, and one of `row`'s said again keeps its type.

        fixed(record, before)   each record as it's kept, given what it was (None: a new one)
        dropped(rows)           the records removed
    """

    TYPES = {str: "string", int: "integer", float: "number", bool: "boolean", datetime: "time"}   # a field's type, by its hint

    def __init__(self, row: type, name: str, db: sqlite3.Connection, kind: str, more: list[dict] = (),
                 fixed: Callable[[dict, Row | None], dict] = lambda record, before: record,
                 dropped: Callable[[list[Row]], None] = lambda rows: None, **rest: Any):
        self.row, self.fixed, self.dropped = row, fixed, dropped
        starts = lambda f: [{"from": "auto", "initial": value}] if (value := self.default(f)) is not None else []
        made   = [Field(f.name, f.metadata["desc"], f.metadata["srcs"] or [{"from": "user"}, *starts(f)], self.typeof(row, f)) for f in fields(row)]
        super().__init__(name, db, kind, [*made, *(Field(**f) for f in more)], record_tables(db, kind), **rest)

    def define(self, f: Field) -> None:
        if f.key in self.row.__dataclass_fields__ and shaped(f.type) != shaped(self.shipped[f.key].type):
            raise ValueError(f"{self.name}.{f.key} is the board's: of type {typename(self.shipped[f.key].type)}")
        super().define(f)

    def put_row(self, record: dict, position: int | None = None, at: datetime | None = None) -> int:
        before, record = self.get_row(dict.get(record, "id")), dict(record)
        if before is None and (missing := [name for name in needed(self.row) if record.get(name) is None]):
            raise VariableError(f"{self.name} needs its {', '.join(missing)}")
        return super().put_row(self.fixed(record, before), position, at)

    def set(self, records: list | None, at: datetime | None = None) -> list[int]:
        kept = {dict.get(record, "id") for record in records} if isinstance(records, list) else set()
        gone = [row for row in self.current() if row["id"] not in kept]
        ids  = super().set(records, at)
        if gone:
            self.dropped(gone)
        return ids

    @staticmethod
    def typeof(row: type, f: Any) -> Type:
        if f.metadata["type"]:
            return f.metadata["type"]
        made = hinted(typing.get_type_hints(row)[f.name])[0]
        return {"type": "array", "items": {"type": Kept.TYPES[typing.get_args(made)[0]]}} if typing.get_origin(made) is list else Kept.TYPES[made]

    @staticmethod
    def default(f: Any) -> Any:
        return f.default_factory() if f.default_factory is not MISSING else None if f.default is MISSING else f.default


class Work(Linked):
    """`work`: the groups, their tasks, the ones at hand and the plan, made once, its names
    again at each build (`make`).

        groups, tasks       the board's records
        ops                 the changes suggested, the first first: ops.create(TaskOp(None, group=3, op="add", fields=...))
        outline(group)      a group as a planner reads it
        tools()             the changes suggested, a tool each: for the app, and an AI agent
    """

    def __init__(self, db: sqlite3.Connection):
        self.db, self.ops = db, TaskOpDB(db)
        self.make()

    def make(self) -> None:
        """`work` and its names, made again."""
        self.groups, self.tasks = self.grouped(), self.tasked()
        fields = {
            "groups": self.groups,
            "group" : Record("work.group", self.groups, "the group at hand: one of work.groups"),
            "tasks" : self.tasks,
            "task"  : Record("work.task", self.tasks, "the task at hand: one of work.tasks"),
            "plan"  : Plan(self),
        }
        read  = lambda: {name: f.current() for name, f in fields.items()}
        typed = {"type": "object", "properties": {name: f.type for name, f in fields.items()}}
        super().__init__("work", read, None, "your groups of tasks, the ones at hand, and the plan", typed)

    def grouped(self) -> Records:
        """work.groups: every group, in your order."""
        return Kept(TaskGr, "work.groups", self.db, "group", SHIPPED["groups"], dropped=self.ungroup, desc="every group, in your order", code={
            "outline"  : ("string",  "the group as a planner reads it: what it's about, and its tasks by their keys", self.outline),
            "suggested": ("integer", "how many changes to its tasks are still suggested", lambda row: len(self.ops.read(group=row["id"]))),
        })

    def tasked(self) -> Records:
        """work.tasks: every task, in your order."""
        opened = lambda table, id: (row := table.get_row(id)) is not None and row["status"] == "open"
        tasks  = Kept(Task, "work.tasks", self.db, "task", SHIPPED["tasks"], self.keyed, self.unsuggest, context=CONTEXT,
                      desc="every task, in your order", code={
            "waiting": ("integer", "how many open tasks need it done first",
                        lambda row: sum(row["id"] in task["after"] for task in tasks.current() if task["status"] == "open")),
            "ready"  : ("boolean", "whether it can be worked on now: open, in an open group, the tasks it needs done first done",
                        lambda row: row["status"] == "open" and opened(self.groups, row["group"]) and not any(opened(tasks, id) for id in row["after"])),
        })
        return tasks

    def keyed(self, task: dict, before: Row | None) -> dict:
        """A task with its key: a new one's from its name. A key changed is checked, and the
        changes suggested follow it. ValueError for another task's key, or not a key."""
        was, to = before and before["key"], task.get("key")
        if before is not None and to == was:  return task
        taken = {t["key"] for t in self.tasks.current() if t["group"] == task.get("group") and t["id"] != task.get("id")}
        if before is None and not to:         return task | {"key": self.unique(task.get("name") or "", taken)}
        if not to or slugify(to) != to:       raise ValueError(f"a key is lowercase words joined by _ ({to!r})")
        if to in taken:                       raise ValueError(f"{to} is another task's key")
        for op in self.ops.read(group=task["group"]) if was else []:
            changed = {"task": to} if op.task == was else {}
            if op.after and was in op.after:  changed["after"] = [to if k == was else k for k in op.after]
            if changed:                       self.ops.update(op.id, **changed)
        return task

    @staticmethod
    def unique(name: str, taken: set[str]) -> str:
        """A new task's key: its name slugified ("task": none), then "_2", "_3"... if it's `taken`."""
        key = slugify(name) or "task"
        return next(k for n in itertools.count(1) if (k := f"{key}_{n}" if n > 1 else key) not in taken)

    def ungroup(self, groups: list[Row]) -> None:
        ids = {group["id"] for group in groups}
        for op in [op for op in self.ops.read() if op.group in ids]:
            self.ops.delete(op.id)
        self.tasks.set([task for task in self.tasks.current() if task["group"] not in ids])

    def unsuggest(self, tasks: list[Row]) -> None:
        for task in tasks:
            for op in self.ops.read(group=task["group"], task=task["key"]):
                self.ops.delete(op.id)

    def outline(self, group: dict) -> str:
        """A group as a planner reads it: what it's about, and its tasks so far by their keys,
        each with what it is and what done looks like (the dropped ones left out)."""
        tasks  = [task for task in self.tasks.current() if task["group"] == group["id"]]
        named  = {task["id"]: task["key"] for task in tasks}
        listed = "\n".join(f"- [{' ' if task['status'] == 'open' else 'x'}] {task['key']}: {task['name']}"
                           + (f" (after {', '.join(named[k] for k in task['after'] if k in named)})" if task["after"] else "")
                           + (f"\n  {task['desc']}" if task["desc"] else "")
                           + (f"\n  done when: {'; '.join(task['done_when'])}" if task["done_when"] else "")
                           for task in tasks if task["status"] != "dropped")
        return (f"It goes with their group of tasks “{group['name']}”: {group['desc'] or '(no description)'}"
                f" (tags: {', '.join(group['tags'] or []) or 'none'})\n\n"
                f"Its tasks so far:\n{listed or '(none yet)'}")

    def tools(self) -> list[Tool]:
        """The changes suggested, a tool each: read them, and add, change or remove one."""
        shape, key = schema(TaskOp, ("id",)), {"id": {"type": "integer"}}
        return [
            Tool("read_ops", "The changes suggested to the groups' tasks, the first suggested first.", {},
                 lambda args: {"ops": [vars(op) for op in self.ops.read()]}, readonly=True),
            Tool("add_op", "A suggested change to a group's tasks, after the others. `op`: add, change or remove. `task`: "
                           "change, remove: its key. `fields`: the task's, add: its name at least. `after`: the keys of "
                           "the tasks it needs done first, ones suggested too. Its id.",
                 shape, lambda args: {"id": self.ops.create(TaskOp(None, **args))}, needed(TaskOp, ("id",))),
            Tool("change_op", "Some of a suggested change's fields.", key | shape,
                 lambda args: self.ops.update(args["id"], **{n: v for n, v in args.items() if n != "id"}), ("id",)),
            Tool("remove_op", "A suggested change taken away: accepted (its task added or changed), or not.", key,
                 lambda args: self.ops.delete(args["id"]), ("id",), undoable=True),
        ]


# --- the plan ---------------------------------------------------------------------------------

GIVES  = {  # the task's fields a change gives
    "name"      : {"type": "string", "description": "the task's name"},
    "desc"      : {"type": "string", "description": "what the task is"},
    "done_when" : TEXTS | {"description": "what done looks like: checks anyone could make"},
    "checkpoint": {"type": "boolean", "description": "whether the task is a check that it all works together"},
    "estimate"  : {"type": "integer", "description": "how long the task takes, in minutes"},
}
CHANGE = {"type": "object", "required": ["op"], "properties": {
    "op"        : {"type": "string", "enum": list(OPS), "description": "add, change or remove"},
    "task"      : {"type": "string", "description": "change, remove: the task's key"},
    **GIVES,
    "after"     : TEXTS | {"description": "the keys of the tasks it needs done first, ones planned too"},
}}
PLAN   = {"type": "object", "properties": {
    "name"      : {"type": "string", "description": "the group's name, as it'd be"},
    "desc"      : {"type": "string", "description": "what the group's for, and where it stands"},
    "tags"      : TAGGED | {"description": "what part of their life it's for, the most likely first"},
    "questions" : TEXTS | {"description": "the open questions only they can answer"},
    "changes"   : {"type": "array", "items": CHANGE, "description": "the changes to the group's tasks"},
}}


class Plan(Linked):
    """work.plan, and a name for each of its fields: what's planned for the group at hand."""

    NAME = "work.plan"
    KEY  = "work_plan"                                               # where its own fields are kept
    KEPT = [key for key in PLAN["properties"] if key != "changes"]   # kept as they are: the changes are a table

    def __init__(self, work: Work):
        self.work, self.kv = work, StateDB(work.db)
        super().__init__(self.NAME, self.read, self.write, "the plan: what's planned for a group, and its changes", PLAN)
        for key, made in PLAN["properties"].items():
            Linked(f"{self.NAME}.{key}", lambda key=key: (self.read() or {}).get(key),
                   lambda value, key=key: self.change(key, value), made.get("description", ""), made)

    def read(self) -> dict[str, Any] | None:
        """The plan, as it is now (None: none)."""
        if (kept := self.kv.get(self.KEY)) is None:
            return None
        shown = lambda op: {"op": op.op, "task": op.task, **{k: op.fields.get(k) for k in GIVES}, "after": op.after}
        return {key: kept.get(key) for key in self.KEPT} | {"changes": [shown(op) for op in self.work.ops.read()]}   # by id: as planned

    def write(self, plan: dict[str, Any] | None) -> None:
        """The plan from now on (None: no plan, its changes taken away)."""
        self.kv.set(self.KEY, None if plan is None else {key: plan.get(key) for key in self.KEPT})
        self.changes((plan or {}).get("changes") or [])

    def change(self, key: str, value: Any) -> None:
        """A field of the plan set (no plan: one made of it)."""
        plan = self.kv.get(self.KEY) or dict.fromkeys(self.KEPT)
        self.kv.set(self.KEY, plan if key == "changes" else plan | {key: value})
        if key == "changes":
            self.changes(value or [])

    def changes(self, given: list[dict]) -> None:
        """Its changes from now on, on the group at hand's card, in place of the ones it had:
        each one the group can take."""
        hand  = Stream.registry.get("work.group")
        group = hand.value if hand else None
        tasks = [task for task in self.work.tasks.current() if task["group"] == group]
        taken = {task["key"] for task in tasks}
        open  = {task["key"] for task in tasks if task["status"] == "open"}
        for op in self.work.ops.read():
            self.work.ops.delete(op.id)
        for change in given:
            if (made := self.made(change, taken, open)) is None:
                continue
            try:
                self.work.ops.create(TaskOp(None, group=group, **made))
            except ValueError as e:
                raise VariableError(f"work.plan: {e}") from None

    @staticmethod
    def made(change: dict, taken: set[str], open: set[str]) -> dict | None:
        """A change, as the board keeps it: its op, task, fields and after (None: one the group
        can't take). An add's key is `taken` from then on."""
        kind  = change.get("op") or "add"
        gives = {k: change[k] for k in GIVES if change.get(k) is not None}
        task  = None
        if kind == "add":
            if not str(gives.get("name") or "").strip():
                return None
            gives["key"] = Work.unique(str(gives["name"]), taken)
            taken.add(gives["key"])
        elif (task := slugify(str(change.get("task") or ""))) not in open:
            return None
        after = change.get("after")
        after = None if after is None else list(dict.fromkeys(k for k in map(slugify, map(str, after)) if k in taken and k != gives.get("key")))
        return {"op": kind, "task": task, "fields": gives, "after": after}
