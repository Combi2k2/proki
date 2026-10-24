"""The popup: what proki asks and tells you.

    await Popup.ask("Start?", ["Start", "Not now"])     →  1: the option picked, by its place
    await Popup.ask("Anything still open?")             →  "milk": what you typed
                                                           (None: no answer, or too late)
    Popup.poke("Back to work")                          a message to read
    Popup.poke("Away?", "Away", "3f9a1c2e")             with its title, and its picks' picture and sound
    Popup.open("tasks/12")                              a page of the app, by its path
    Popup.send({"type": "status", ...})                 any other: "status" (the tray's line), "quit"

A question can also say how it's shown:

    id="3f9a1c2e"       a picture and a sound, drawn from its picks
    urgent=True         before the questions waiting their turn
    text="..."          what's typed already
    title="Bedtime"     its heading
    immediate=True      to answer now: no "Later"

One question is shown at a time, the others waiting their turn. One no longer asked leaves
the screen, and a sound plays only while its question or message is on it.
"""

from __future__ import annotations

import asyncio
import itertools
from typing import Any, ClassVar

from proki.channels.base import Channels, Options, Question, paired, text
from proki.utils import numeric


class Popup:
    POOL : ClassVar[str] = "questions"                      # its pool every question draws from, along with its own
    lib  : ClassVar[Any] = None                             # the media library, drawn from      
    ids  : ClassVar[itertools.count] = itertools.count(1)   # a question's id, to take it back

    # --- asking ------------------------------------------------------------------------------

    @staticmethod
    async def ask(context: str, options: Options | None = None, timeout: float = 120, id: str | None = None, **show: Any) -> int | str | None:
        """Your answer: the option picked, by its place, or with no options what you typed
        (None: no answer)."""
        asked = next(Popup.ids)
        show = {k: v for k, v in show.items() if v is not None} | Popup.draw(id, Popup.POOL)

        answer = None
        try:
            answer = await UsrQuestion(context, options, timeout, asked, show).invoke()
        finally:
            if answer is None:  # no answer, or no longer asked: off the screen (and its sound stops), before it says so
                await asyncio.shield(Channels.bus.publish("proki.ui", {"type": "cancel", "id": asked}))
        return answer

    # --- telling -----------------------------------------------------------------------------

    @staticmethod
    def send(message: dict) -> None:
        """A message to the app, nothing back, in the order sent."""
        asyncio.get_running_loop().create_task(Channels.bus.publish("proki.ui", message))

    @staticmethod
    def poke(text: str, title: str | None = None, id: str | None = None) -> None:
        """A message to read: its title, and a picture and a sound from its picks."""
        Popup.send({"type": "poke", "text": text, **({"title": title} if title else {}), **Popup.draw(id)})

    @staticmethod
    def draw(id: str | None, pool: str | None = None) -> dict[str, str]:
        """A picture and a sound, drawn from the picks of `id` and `pool`: {"media", "sound"},
        each as its file (none: left out)."""
        lib = Popup.lib
        if lib is None:  return {}

        keys  = [*(lib.get_pool(pool) if pool else []), *(lib.get_picks(id) if id else [])]
        drawn = {"media": lib.draw(keys, "image"), "sound": lib.draw(keys, "sound")}
        return {name: file for name, file in drawn.items() if file}

    @staticmethod
    def open(path: str) -> None:
        """A page of the app opened, by its path ("tasks/12")."""
        Popup.send({"type": "open", "path": path})


class UsrQuestion(Question):
    """A question to you (`Popup.ask`)."""

    CHANNEL = "usr"
    KEEP    = False   # you're asked each time

    def __init__(self, context: str, options: Options | None, timeout: float, id: int, show: dict):
        super().__init__(context, timeout)
        self.options = [list(o) for o in paired(options)] if options else None   # none, or an empty list: a text
        self.id, self.show = id, show

    def resolve_input(self) -> dict:
        return {"id": self.id, "context": self.context, "options": self.options, "show": self.show}

    def resolve_output(self, answer: Any) -> int | str | None:
        if self.options is None:
            return text(answer)
        return int(answer) if numeric(answer) and answer == int(answer) and 0 <= answer < len(self.options) else None
