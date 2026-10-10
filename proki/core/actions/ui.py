"""Actions on the UI, one way (nothing comes back):

    {"poke": {"context": "Back to work"}}            a message to read (a question is `ask`, ask.py)
    {"poke": {"context": {"format": "{n} pokes today", "values": {"n": "pokes"}}}}
    {"alarm": {"name": "bedtime", "on": true}}       ring alarm "bedtime" (true) until it's turned off (false)
    {"lock": {}}                                     lock the screen
    {"open": {"view": "task_form"}}                  open a view: task_form (a new task), task_board

A poke's `context` is filled in as it's said (base.py: `Context`). Each alarm goes by its
own name, so turning one off leaves the others.

Each kind has a `handler`, what does it, set by the app (None: nothing happens):

    Poke.handler(text)          show a message
    Alarm.handler(name, on)     ring alarm `name`, or stop it
    Lock.handler()              lock the screen
    Open.handler(view)          open one of the app's views
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from proki.core.actions.base import Action, Context
from proki.errors import ActionError

VIEWS = ("task_form", "task_board")


class Poke(Action):
    handler: ClassVar[Callable[[str], None] | None] = None

    def __init__(self, context: str | dict):
        self.context = Context(context, "poke")

    async def apply(self) -> None:
        if Poke.handler is not None:
            Poke.handler(self.context.said())

    def __repr__(self) -> str:
        return f"poke {self.context!r}"


class Alarm(Action):
    handler: ClassVar[Callable[[str, bool], None] | None] = None

    def __init__(self, name: str, on: bool):
        if not isinstance(name, str) or not name:   raise ActionError(f"alarm: name is the alarm's name ({name!r})")
        if not isinstance(on, bool):                raise ActionError(f"alarm {name!r}: on is true (ring) or false (stop) ({on!r})")
        self.name, self.on = name, on

    async def apply(self) -> None:
        if Alarm.handler is not None:
            Alarm.handler(self.name, self.on)

    def __repr__(self) -> str:
        return f"alarm {self.name} {'on' if self.on else 'off'}"


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
