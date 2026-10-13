"""Actions on the UI, one way (nothing comes back):

    {"poke": {"context": "Back to work"}}            a message to read (a question is `ask`, ask.py)
    {"poke": {"context": {"format": "{n} pokes today", "values": {"n": "pokes"}}}}
    {"poke": {"context": "You've been away", "title": "Away", "media": ["bugcat/what"], "sound": ["alarm-clock"]}}
    {"lock": {}}                                     lock the screen
    {"open": {"view": "task_form"}}                  open a view: task_form (a new task), task_board

A poke's `context` is filled in as it's said (base.py: `Context`). Its `title` is a
heading, and `media` and `sound` are what it may show and play: keys of the media library
(the app's), one of each drawn as it's shown (base.py: `Display`, a question's too). A
sound plays while the poke is on the screen, and stops as it's closed: a reminder for when
you may not be looking.

Each kind has a `handler`, what does it, set by the app (None: nothing happens):

    Poke.handler(text, title, media, sound)   show a message: its heading, and the keys to
                                              draw a picture and a sound from
    Lock.handler()              lock the screen
    Open.handler(view)          open one of the app's views
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from proki.core.actions.base import Action, Context, Display
from proki.errors import ActionError

VIEWS = ("task_form", "task_board")


class Poke(Action):
    handler: ClassVar[Callable[..., None] | None] = None

    def __init__(self, context: str | dict, title: str | None = None, media: list | None = None, sound: list | None = None):
        self.context = Context(context, "poke")
        self.display = Display("poke", title, media, sound)

    def reads(self) -> list[str]:
        return list(self.context.values.values())

    async def apply(self) -> None:
        if Poke.handler is not None:
            Poke.handler(self.context.said(), **self.display.shown())

    def __repr__(self) -> str:
        return f"poke {self.context!r}" + (f" ({self.display.title})" if self.display.title else "")


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
