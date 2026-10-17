"""Your work, as a board: projects, a card each, of tasks, the atomic things to do.

    Project   a piece of work: what it's about (`desc`), the questions only you can answer
              yet, its tags, estimate and deadline, its tasks
    Task      one thing to do, in a sitting: what it is (`desc`), what "done" looks like
              (`done_when`, three checks at most), the tasks it needs done first (`after`),
              your notes on it (`note`), its estimate and deadline. A checkpoint is a short
              one to check it all works together, and decide what's next
    Work      the board as it is now, read at once
    Board     the tables (in proki.db), kept together

A project's tags say what part of your life it's for, the most likely first, three at most
(`MAX_TAGS`): "papers", "visa". Each is a part of a row of the board ("study", "admin":
assets/tags.json), and the first one's row is where the project's card is. It goes to another
row only if one of its tags is in it. A project without tags has a row of its own.

Each is in your order (`position`): the projects all together, each project's tasks within
it. A task's deadline is its own, or else its project's. Without either, it has none. A task
is ready once the tasks it needs are done (or dropped).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field, replace
from datetime import datetime

from proki import settings
from proki.programs.code.base import Table

ROWS     = json.loads((settings.ASSETS_DIR / "tags.json").read_text())                # each row, and its tags
ROW      = {tag: row for row, tags in reversed(ROWS.items()) for tag in tags}        # each tag's row: the first it's in
TAGS     = list(dict.fromkeys(tag for tags in ROWS.values() for tag in tags))        # each tag, once
ESTIMATE = 25                                                                        # minutes: a task's, until you say
MAX_TAGS = 3


# --- the board's rows -------------------------------------------------------------------------

@dataclass
class Project:
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
    project    : int
    name       : str
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


@dataclass
class Work:
    projects : list[Project]
    tasks    : list[Task]
    of       : dict[int, Project] = field(init=False)   # each task's project, by the project's id

    def __post_init__(self):
        self.of = {project.id: project for project in self.projects}

    def open(self) -> list[Task]:
        """The open tasks of the open projects, in your order."""
        return sorted((task for task in self.tasks if task.status == "open" and self.of[task.project].status == "open"),
                      key=lambda task: (self.of[task.project].position, task.position))

    def ready(self) -> list[Task]:
        """The open tasks whose `after` are all done or dropped, in your order."""
        closed = {task.id for task in self.tasks if task.status != "open"}
        known  = {task.id for task in self.tasks}
        return [task for task in self.open() if all(need in closed or need not in known for need in task.after)]

    def deadline(self, task: Task) -> datetime | None:
        """Its own deadline, or else its project's."""
        return task.deadline or self.of[task.project].deadline


# --- the board --------------------------------------------------------------------------------

class ProjectDB(Table[Project]):
    NAME = "projects"


class TaskDB(Table[Task]):
    NAME = "tasks"


class Board:
    """The projects and their tasks, each a "project" or a "task" (its `kind`). Each change
    keeps when (`at`): a new one's `created_at`, and `updated_at`. A `status` other than
    "open" keeps its `done_at`.

        read()                                  the work as it is now
        add("task", at, project=3, name=...)    a new one, last: a project on the board, a task
                                                in its project. Its id
        change("task", 7, at, name=...)         some of its fields
        remove("project", 7)                    with its tasks
        move("task", 7, at, before=9)           before task 9 of its project (None: last)
        move("project", 7, at, row="study")     into the row of one of its tags (that tag first),
                                                before `before`
    """

    KINDS = {"project": Project, "task": Task}   # each kind's row

    def __init__(self, db: sqlite3.Connection):
        self.tables = {"project": ProjectDB(db), "task": TaskDB(db)}

    def read(self) -> Work:
        projects, tasks = (sorted(table.read(), key=lambda row: row.position) for table in self.tables.values())
        return Work(projects, tasks)

    def add(self, kind: str, at: datetime | None = None, **fields) -> int:
        row = self.KINDS[kind](None, **fields, created_at=at, updated_at=at)   # a project checks its tags
        return self.tables[kind].create(replace(row, position=len(self.around(row))))

    def change(self, kind: str, key: int, at: datetime | None = None, **fields) -> None:
        if "tags" in fields:    Project(key, "", tags=fields["tags"])   # checked as a project's (the table makes none)
        if "status" in fields:  fields["done_at"] = at if fields["status"] != "open" else None
        self.tables[kind].update(key, **fields, updated_at=at)

    def remove(self, kind: str, key: int) -> None:
        if kind == "project":
            for task in self.tables["task"].read(project=key):  self.tables["task"].delete(task.id)
        self.tables[kind].delete(key)

    def move(self, kind: str, key: int, at: datetime | None = None, before: int | None = None, row: str | None = None) -> None:
        """Before the one keyed `before`, or last. A project into `row`, if one of its tags is in it."""
        [moved] = self.tables[kind].read(key)
        if kind == "project" and row is not None:
            first = next((tag for tag in moved.tags if ROW[tag] == row), None)
            if first is None:  raise ValueError(f"{moved.name!r} has no tag in {row!r}")
            moved = replace(moved, tags=[first, *(tag for tag in moved.tags if tag != first)])

        rest  = [other for other in self.around(moved) if other.id != key]
        place = next((i for i, other in enumerate(rest) if other.id == before), len(rest))
        for position, other in enumerate([*rest[:place], moved, *rest[place:]]):
            self.tables[kind].create(replace(other, position=position, updated_at=at if other is moved else other.updated_at))

    def around(self, row: Project | Task) -> list:
        """The ones in order with it: all the projects, or its project's tasks."""
        found = self.tables["task"].read(project=row.project) if isinstance(row, Task) else self.tables["project"].read()
        return sorted(found, key=lambda other: other.position)
