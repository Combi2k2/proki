"""The popup: everything proki says to you, through the UI (ui/main.js).

Asking, on the "usr" channel ("proki.ask.usr"): the question waits for your answer, and
the answer goes back to whoever asked. That one does what it means.

    await Popup.ask("Start?", ["Start", "Not now"])               1         the option's index
    await Popup.ask("Anything still open?")                       "milk"    the text you typed
                                                                  None      dismissed, or too late

    what it may show and play, keys of the media library (one of each drawn as it's asked):
        media=["bugcat/sad"]     its own pictures, drawn along with the "questions" pool
        sound=["alarm-clock"]    its own sounds: one plays while it's shown

    how it's shown (`show`):
        urgent=True          before the questions waiting their turn
        text="..."           what's typed already
        title="Bedtime"      its heading

Telling, one way ("proki.ui"): nothing comes back.

    Popup.poke("Back to work")      {"type": "poke", "text": ...}            a message to read
    Popup.poke("Away?", "Away", ["bugcat/what"], ["alarm-clock"])           a title, and a picture and a
                                                                             sound drawn from those keys
    Popup.open("task_form")         {"type": "open", "view": ...}            a view: task_form, task_board
    Popup.send({"type": ...})       any other:
                                    "status"   the tray's line, each cycle
                                    "quit"     the UI closes
                                    "cancel"   a question no longer asked (`ask` sends it)

The UI shows one question at a time: the others wait their turn, and one that's too late,
or no longer asked (whoever asked moved on), leaves the line ("cancel"). A sound plays
only while its question or poke is on the screen: closing it stops the sound at once.
Whether a question waits is the channel's (`queued("usr")`, base.py).

Pictures and sounds are drawn from the media library (`library`, services/media.py: the app
sets it), and sent as their files. Without one, none.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from proki.channels.base import (
    Channels,
    Options,
    paired,
    picked,
    request
)

class Popup:
    library: ClassVar[Any] = None  # the media library (services/media.py), drawn from
    POOL   : ClassVar[str] = "questions"  # its pool every question draws from, along with its own

    # --- asking ------------------------------------------------------------------------------

    @staticmethod
    async def ask(context: str, options: Options | None = None, timeout: float = 120,
                  media: list[str] = (), sound: list[str] = (), **show: Any) -> int | str | None:
        """Your answer: an option's index, or with no options the text you typed. None when
        there's no answer, and then the question is taken off the screen."""
        id = next(Channels.ids)
        show = {k: v for k, v in show.items() if v is not None}
        if Popup.library is not None:
            show |= Popup.draw(media=[*Popup.library.get_pool(Popup.POOL), *media], sound=list(sound))

        try:
            options = None if options is None else paired(options)
            answer = await request("usr", {"id": id, "context": context, "options": options, "show": show}, timeout)
        except asyncio.CancelledError:  # no longer asked: off the screen (and its sound stops)
            Popup.send({"type": "cancel", "id": id})
            raise

        if answer is None:       await Channels.bus.publish("proki.ui", {"type": "cancel", "id": id})
        if options is not None:  return picked(answer, options)
        return answer if isinstance(answer, str) and answer.strip() else None

    # --- telling -----------------------------------------------------------------------------

    @staticmethod
    def send(message: dict) -> None:
        """A one-way message. Sent on the engine's loop, in the order sent."""
        asyncio.get_running_loop().create_task(Channels.bus.publish("proki.ui", message))

    @staticmethod
    def poke(text: str, title: str | None = None, media: list[str] = (), sound: list[str] = ()) -> None:
        """A message to read: its `title`, and a picture and a sound drawn from the keys of
        `media` and `sound` (as their files)."""
        drawn = Popup.draw(media=list(media), sound=list(sound)) if Popup.library is not None else {}
        Popup.send({"type": "poke", "text": text, **({"title": title} if title else {}), **drawn})

    @staticmethod
    def draw(**keys: list[str]) -> dict[str, str]:
        """One file of each list of keys, drawn from the library: {"media": file, ...}
        (a list with none in the library: left out)."""
        return {name: file for name, among in keys.items() if (file := Popup.library.draw(among))}

    @staticmethod
    def open(view: str) -> None:
        Popup.send({"type": "open", "view": view})
