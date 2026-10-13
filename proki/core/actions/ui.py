"""Actions on the UI, one way (nothing comes back):

    {"poke": {"context": "Back to work"}}            a message to read (a question is `ask`, ask.py)
    {"poke": {"context": {"format": "{n} pokes today", "values": {"n": "pokes"}}}}
    {"poke": {"context": "You've been away", "title": "Away"}}
    {"lock": {}}                                     lock the screen
    {"open": {"view": "task_form"}}                  open a view: task_form (a new task), task_board

A poke's `context` is filled in as it's said (base.py: `Context`), and its `title` is a
heading. As it's shown, a picture and a sound are drawn from its picks (the media library's,
by the action's `id`). The sound plays until the poke is closed: a reminder for when you may
not be looking.

Each kind has a `handler`, what does it, set by the app (None: nothing happens):

    Poke.handler(text, title, id)   show a message, its heading, and what it draws from
    Lock.handler()                  lock the screen
    Open.handler(view)              open one of the app's views
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from proki.core.actions.base import Action, Context
from proki.errors import ActionError

VIEWS = ("task_form", "task_board")


class Poke(Action):
    handler: ClassVar[Callable[..., None] | None] = None

    def __init__(self, context: str | dict, title: str | None = None):
        if title is not None and (not isinstance(title, str) or not title):  raise ActionError(f"poke: title is a text ({title!r})")

        self.context = Context(context, "poke")
        self.title   = title

    def reads(self) -> list[str]:
        return list(self.context.values.values())

    async def apply(self) -> None:
        if Poke.handler is not None:
            Poke.handler(self.context.said(), title=self.title, id=self.id)

    def __repr__(self) -> str:
        return f"poke {self.context!r}" + (f" ({self.title})" if self.title else "")


class Lock(Action):
    handler: ClassVar[Callable[[], None] | None] = None

    def __init__(self):
        pass

    async def apply(self) -> None:
        if Lock.handler is not None:
            Lock.handler()

    def __repr__(self) -> str:
        return "lock"


class Open(Action):
    handler: ClassVar[Callable[[str], None] | None] = None

    def __init__(self, view: str):
        if view not in VIEWS:  raise ActionError(f"open: view is one of {', '.join(VIEWS)} ({view!r})")
        self.view = view

    async def apply(self) -> None:
        if Open.handler is not None:
            Open.handler(self.view)

    def __repr__(self) -> str:
        return f"open {self.view}"
