"""Your work, as a board: groups of tasks, a card each, the tasks the atomic things to do.

    TaskGr    a group of tasks: a project, or what an errand takes. What it's about (`desc`),
              the questions only you can answer yet, its tags, estimate and deadline, its
              tasks
    Task      one thing to do, in a sitting, by its handle in its group (its name slugified,
              kept as it's renamed): what it is (`desc`), what "done" looks like
              (`done_when`, three checks at most), the tasks it needs done first (`after`),
              your notes on it (`note`), its estimate and deadline. A checkpoint is a short
              one to check it all works together, and decide what's next
    TaskOp    a change to a group's tasks, suggested for you to accept or not: add a task,
              change or remove one, each task by its handle. One can be made once each task
              it says is there: an add after another, once that one's accepted
    Work      the board as it is now, read at once
    Board     the tables (in proki.db), kept together

A group's tags say what part of your life it's for, the most likely first, three at most
(`MAX_TAGS`): "papers", "visa". Each is a part of a row of the board ("study", "admin":
assets/tags.json), and the first one's row is where the group's card is. It goes to another
row only if one of its tags is in it. A group without tags has a row of its own.

Each is in your order (`position`): the groups all together, each group's tasks within
it. A task's deadline is its own, or else its group's. Without either, it has none. A task
is ready once the tasks it needs are done (or dropped).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field, fields, replace
from datetime import UTC, datetime

from proki import settings
from proki.programs.code.base import Table
from proki.typehint import needed, plain, schema, typed
from proki.tools.base import Tool
from proki.utils import slugify

ROWS     = json.loads((settings.ASSETS_DIR / "tags.json").read_text())                # each row, and its tags
ROW      = {tag: row for row, tags in reversed(ROWS.items()) for tag in tags}        # each tag's row: the first it's in
TAGS     = list(dict.fromkeys(tag for tags in ROWS.values() for tag in tags))        # each tag, once
ESTIMATE = 25                                                                        # minutes: a task's, until you say
MAX_TAGS = 3
AUTO     = ("id", "position", "created_at", "updated_at", "done_at")                 # what the board keeps itself
SAYS     = {                                                                         # what each tool does, for who calls it
    "add_group":    "A new group, last on the board. `tags`: what part of your life it's for, the most likely "
                      "first, 3 at most, each one of a row's (read_board). Its id.",
    "add_task":       "A new task, last in its group. `after`: the ids of the tasks it needs done first. "
                      "`done_when`: what done looks like, 3 checks at most. Its id.",
    "change_group": "Some of a group's fields. `status`: open, done, or dropped (set aside, kept).",
    "change_task":    "Some of a task's fields. `status`: open, done, or dropped (set aside, still on its card).",
    "remove_group": "A group deleted, with its tasks. To set it aside instead, change its status to dropped.",
    "remove_task":    "A task deleted. To set it aside instead, change its status to dropped.",
    "move_group":   "A group before another (`before`, its id; none: last). `row`: into the row of one of its "
                      "tags, that tag first.",
    "move_task":      "A task before another of its group (`before`, its id; none: last).",
    "add_op":         "A suggested change to a group's tasks, after the others. `op`: add, change or remove. "
                      "`task`: change, remove: its handle. `fields`: the task's, add: its name at least. `after`: "
                      "the handles of the tasks it needs done first, ones suggested too. Its id.",
    "change_op":      "Some of a suggested change's fields.",
    "remove_op":      "A suggested change taken away: accepted (made with add_task or change_task), or not.",
}
OPS      = ("add", "change", "remove")


# --- the board's rows -------------------------------------------------------------------------

@dataclass
class TaskGr:
    id         : int | None
    name       : str
    desc       : str             = ""
    questions  : list[str]       = field(default_factory=list)   # open, only you can answer them
    tags       : list[str]       = field(default_factory=list)   # the most likely first
    estimate   : int | None      = None     # minutes, all of it (None: not said)
    deadline   : datetime | None = None
    status     : str             = "open"   # "open", "done" or "dropped"
    position   : int             = 0
    created_at : datetime | None = None
    updated_at : datetime | None = None
    done_at    : datetime | None = None

    def __post_init__(self):
        """Its tags are known ones, `MAX_TAGS` at most."""
        if unknown := [tag for tag in self.tags if tag not in ROW]:  raise ValueError(f"no tag {', '.join(unknown)}")
        if len(self.tags) > MAX_TAGS:                                raise ValueError(f"{MAX_TAGS} tags at most")

    @property
    def row(self) -> str | None:
        """The row its card is in: its first tag's (None: it has no tags)."""
        return ROW[self.tags[0]] if self.tags else None


@dataclass
class Task:
    id         : int | None
    group      : int
    name       : str
    handle     : str             = ""         # its name slugified, one of its group's (given as it's added)
    desc       : str             = ""
    done_when  : list[str]       = field(default_factory=list)   # what "done" looks like: checks anyone could make
    after      : list[int]       = field(default_factory=list)   # the tasks it needs done first, by their ids
    checkpoint : bool            = False      # a check it all works together, and what's next
    note       : str             = ""
    estimate   : int             = ESTIMATE   # minutes
    deadline   : datetime | None = None
    status     : str             = "open"     # "open", "done" or "dropped"
    position   : int             = 0
    created_at : datetime | None = None
    updated_at : datetime | None = None
    done_at    : datetime | None = None


OP_FIELDS = [f.name for f in fields(Task) if f.name not in (*AUTO, "group", "after", "status")]   # a task's, an op gives


@dataclass
class TaskOp:
    id         : int | None
    group      : int
    op         : str                                             # "add", "change" or "remove"
    task       : str | None       = None                         # change, remove: the task's handle
    fields     : dict             = field(default_factory=dict)  # the task's fields it gives (add: its handle too)
    after      : list[str] | None = None                         # the tasks it needs done first, by their handles

    def __post_init__(self):
        """An op there is: an add with a name, a change or a removal of a task, and a task's fields."""
        if self.op not in OPS:                                  raise ValueError(f"no op {self.op!r}")
        if self.op == "add" and not self.fields.get("name"):    raise ValueError("an add needs a name")
        if self.op != "add" and self.task is None:              raise ValueError(f"a {self.op} needs a task")
        if unknown := set(self.fields) - set(OP_FIELDS):        raise ValueError(f"no field {', '.join(sorted(unknown))} to give")


def unique(handle: str, taken: set[str]) -> str:
    """The handle, or "_2", "_3"... after it, if it's taken."""
    n = 1
    while (fresh := handle if n == 1 else f"{handle}_{n}") in taken:
        n += 1
    return fresh


@dataclass
class Work:
    groups : list[TaskGr]
    tasks  : list[Task]
    ops    : list[TaskOp]      = field(default_factory=list)
    of     : dict[int, TaskGr] = field(init=False)   # each task's group, by the group's id

    def __post_init__(self):
        self.of = {group.id: group for group in self.groups}

    def open(self) -> list[Task]:
        """The open tasks of the open groups, in your order."""
        return sorted((task for task in self.tasks if task.status == "open" and self.of[task.group].status == "open"),
                      key=lambda task: (self.of[task.group].position, task.position))

    def ready(self) -> list[Task]:
        """The open tasks whose `after` are all done or dropped, in your order."""
        closed = {task.id for task in self.tasks if task.status != "open"}
        known  = {task.id for task in self.tasks}
        return [task for task in self.open() if all(need in closed or need not in known for need in task.after)]

    def deadline(self, task: Task) -> datetime | None:
        """Its own deadline, or else its group's."""
        return task.deadline or self.of[task.group].deadline


# --- the board --------------------------------------------------------------------------------

class TaskGrDB(Table[TaskGr]):
    NAME = "task_groups"


class TaskDB(Table[Task]):
    NAME = "tasks"


class TaskOpDB(Table[TaskOp]):
    NAME = "task_ops"


class Board:
    """The groups, their tasks and the ops suggested on them, each a "group", a "task" or
    an "op" (its `kind`). The ops are in the order they're suggested, with no times. Each change
    keeps when (`at`): a new one's `created_at`, and `updated_at`. A `status` other than
    "open" keeps its `done_at`.

        read()                                  the work as it is now
        add("task", at, group=3, name=...)    a new one, last: a group on the board, a task
                                                in its group. Its id
        change("task", 7, at, name=...)         some of its fields
        remove("group", 7)                    with its tasks
        move("task", 7, at, before=9)           before task 9 of its group (None: last)
        move("group", 7, at, row="study")     into the row of one of its tags (that tag first),
                                                before `before`
        tools()                                 each of these, a `Tool`: for the UI, and an AI agent
    """

    KINDS = {"group": TaskGr, "task": Task, "op": TaskOp}   # each kind's row

    def __init__(self, db: sqlite3.Connection):
        self.tables = {"group": TaskGrDB(db), "task": TaskDB(db), "op": TaskOpDB(db)}

    def read(self) -> Work:
        groups = sorted(self.tables["group"].read(), key=lambda row: row.position)
        tasks  = sorted(self.tables["task"].read(),  key=lambda row: row.position)
        return Work(groups, tasks, self.tables["op"].read())

    def add(self, kind: str, at: datetime | None = None, **fields) -> int:
        if kind == "op":
            return self.tables["op"].create(TaskOp(None, **fields))
        if kind == "task":
            taken = {task.handle for task in self.tables["task"].read(group=fields["group"])}
            fields["handle"] = unique(fields.get("handle") or slugify(fields["name"]) or "task", taken)
        row = self.KINDS[kind](None, **fields, created_at=at, updated_at=at)   # a group checks its tags
        return self.tables[kind].create(replace(row, position=len(self.around(row))))

    def change(self, kind: str, key: int, at: datetime | None = None, **fields) -> None:
        if "tags" in fields:    TaskGr(key, "", tags=fields["tags"])   # checked as a group's (the table makes none)
        if "status" in fields:  fields["done_at"] = at if fields["status"] != "open" else None
        if kind == "op":  # checked as an op's, as it's read back (a field it hasn't: the table says so)
            [op] = self.tables["op"].read(key)
            replace(op, **{name: value for name, value in fields.items() if hasattr(op, name)})
        self.tables[kind].update(key, **fields, **({} if kind == "op" else {"updated_at": at}))

    def remove(self, kind: str, key: int) -> None:
        if kind == "group":
            for task in self.tables["task"].read(group=key):  self.tables["task"].delete(task.id)
            for op in self.tables["op"].read(group=key):      self.tables["op"].delete(op.id)
        if kind == "task":
            [task] = self.tables["task"].read(key)
            for op in self.tables["op"].read(group=task.group, task=task.handle):  self.tables["op"].delete(op.id)
        self.tables[kind].delete(key)

    def move(self, kind: str, key: int, at: datetime | None = None, before: int | None = None, row: str | None = None) -> None:
        """Before the one keyed `before`, or last. A group into `row`, if one of its tags is in it."""
        [moved] = self.tables[kind].read(key)
        if kind == "group" and row is not None:
            first = next((tag for tag in moved.tags if ROW[tag] == row), None)
            if first is None:  raise ValueError(f"{moved.name!r} has no tag in {row!r}")
            moved = replace(moved, tags=[first, *(tag for tag in moved.tags if tag != first)])

        rest  = [other for other in self.around(moved) if other.id != key]
        place = next((i for i, other in enumerate(rest) if other.id == before), len(rest))
        for position, other in enumerate([*rest[:place], moved, *rest[place:]]):
            self.tables[kind].create(replace(other, position=position, updated_at=at if other is moved else other.updated_at))

    def around(self, row: TaskGr | Task) -> list:
        """The ones in order with it: all the groups, or its group's tasks."""
        found = self.tables["task"].read(group=row.group) if isinstance(row, Task) else self.tables["group"].read()
        return sorted(found, key=lambda other: other.position)

    # --- its tools ----------------------------------------------------------------------------

    def tools(self) -> list[Tool]:
        """What the board can do, a tool each: read it, and add, change, remove or move a group
        or a task. A tool's arguments are a group's or a task's fields, but its id, place and
        times: the board keeps those itself."""
        def read(args: dict) -> dict:
            work = self.read()
            return {"groups": [plain(p) for p in work.groups], "tasks": [plain(t) for t in work.tasks],
                    "ops": [plain(o) for o in work.ops], "rows": ROWS}

        return [
            Tool("read_board", "The board: its groups, tasks and suggested ops, in your order, and its rows, each with its tags.",
                 {}, read, reads=True),
            *self.tools_of("group"),
            *self.tools_of("task"),
            *self.tools_of("op"),   # in their order: not moved
        ]

    def tools_of(self, kind: str) -> list[Tool]:
        """A kind's tools: add, change, remove and move (the ones it has: `SAYS`)."""
        row, now = self.KINDS[kind], lambda: datetime.now(UTC)
        shape    = schema(row, AUTO)
        key      = {"id": {"type": "integer"}}
        place    = {"before": {"type": ["integer", "null"]}} | ({"row": {"type": "string"}} if kind == "group" else {})
        changes  = lambda args: typed(row, {name: value for name, value in args.items() if name != "id"})
        made     = [
            Tool(f"add_{kind}",    SAYS.get(f"add_{kind}"), {n: s for n, s in shape.items() if n != "status"},
                 lambda args: {"id": self.add(kind, now(), **typed(row, args))}, needed(row, AUTO)),
            Tool(f"change_{kind}", SAYS.get(f"change_{kind}"), key | shape,
                 lambda args: self.change(kind, args["id"], now(), **changes(args)), ("id",)),
            Tool(f"remove_{kind}", SAYS.get(f"remove_{kind}"), key,
                 lambda args: self.remove(kind, args["id"]), ("id",), destroys=True),
            Tool(f"move_{kind}",   SAYS.get(f"move_{kind}"), key | place,
                 lambda args: self.move(kind, args["id"], now(), args.get("before"), args.get("row")), ("id",)),
        ]
        return [tool for tool in made if tool.name in SAYS]
