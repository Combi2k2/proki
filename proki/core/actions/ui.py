"""Actions on the UI, nothing coming back:

    {"poke": {"context": "You've been away", "title": "Away"}}   a message, a heading optional
    {"lock": {}}                                                 the screen locked
    {"open": {"path": "'tasks/' + str(work.group.id)"}}          a page of the app opened: its view
                                                                 (today, tasks, notes, apps, metrics,
                                                                 programs, media), then what in it

A poke shows a picture and plays a sound until it's closed: for when you may not be looking.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from proki.core.actions.base import Action, Context, RValue
from proki.errors import ActionError

# each kind's handler is what does it, given by the app (None: nothing happens)


class Poke(Action):
    ABOUT   = ("a message in the popup, nothing to answer: a title. It gets an id as it's added: one picture "
               "and one sound are drawn from its picks (set_picks), a sound playing while it's shown")
    EXAMPLE = {"poke": {"context": {"format": "{h:.0f} h left today", "values": {"h": "(deadline_eod - time) / 60"}}, "title": "Today"}}
    handler : ClassVar[Callable[..., None] | None] = None   # (text, title, id): the id, what its picture and sound are drawn from

    def __init__(self, context: Context, title: str | None = None):
        if title is not None and (not isinstance(title, str) or not title):
            raise ActionError(f"poke: title is a text ({title!r})")
        self.context = Context(context, "poke")
        self.title   = title

    def read(self) -> list[RValue]:
        return list(self.context.values.values())

    async def apply(self) -> None:
        if Poke.handler is not None:
            Poke.handler(self.context.said(), title=self.title, id=self.id)

    def __repr__(self) -> str:
        return f"poke {self.context!r}" + (f" ({self.title})" if self.title else "")


class Lock(Action):
    ABOUT   = "lock the screen"
    EXAMPLE = {"lock": {}}
    handler : ClassVar[Callable[[], None] | None] = None

    def __init__(self):
        pass

    async def apply(self) -> None:
        if Lock.handler is not None:
            Lock.handler()

    def __repr__(self) -> str:
        return "lock"


class Open(Action):
    ABOUT   = "open a page of the UI by its path, an expression: its view, then what in it ('tasks/12': group 12's card)"
    EXAMPLE = {"open": {"path": "'tasks/' + str(work.group.id)"}}
    handler : ClassVar[Callable[[str], None] | None] = None

    def __init__(self, path: RValue):
        if not isinstance(path, str) or not path.strip():
            raise ActionError(f"open: path is an expression ({path!r})")
        self.path = RValue(path)

    async def apply(self) -> None:
        if Open.handler is not None and isinstance(path := self.path.value(), str) and path:
            Open.handler(path)

    def read(self) -> list[RValue]:
        return [self.path]

    def __repr__(self) -> str:
        return f"open {self.path}"
