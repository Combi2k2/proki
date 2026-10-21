"""The popup: everything proki says to you, through the UI.

Asking, on the "usr" channel ("proki.ask.usr"): the question waits for your answer, and
the answer goes back to whoever asked. That one does what it means.

    await Popup.ask("Start?", ["Start", "Not now"])               1         the option's index
    await Popup.ask("Anything still open?")                       "milk"    the text you typed
                                                                  None      dismissed, or too late

    what it may show and play, one picture and one sound drawn as it's asked:
        id="3f9a1c2e"        its action's picks in the media library, and the
                             "questions" pool

    how it's shown (`show`):
        urgent=True          before the questions waiting their turn
        text="..."           what's typed already
        title="Bedtime"      its heading
        immediate=True       to answer now: no "Later"

    An option "OK" or "Later" is that button itself (ui/src/pages/popup.tsx).

Telling, one way ("proki.ui"): nothing comes back.

    Popup.poke("Back to work")      {"type": "poke", "text": ...}            a message to read
    Popup.poke("Away?", "Away", "3f9a1c2e")                                 a title, and a picture and a
                                                                             sound drawn from its picks
    Popup.open("tasks")             {"type": "open", "view": ...}            a view of the app: today, tasks, ...
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
from collections.abc import Sequence
from typing import Any, ClassVar

from proki.channels.base import Channels, request

Options = Sequence[str | tuple[str, str | None]]  # "Start", or ("Start", what it means)


class Popup:
    library: ClassVar[Any] = None  # the media library (services/media.py), drawn from
    POOL   : ClassVar[str] = "questions"  # its pool every question draws from, along with its own

    # --- asking ------------------------------------------------------------------------------

    @staticmethod
    async def ask(context: str, options: Options | None = None, timeout: float = 120,
                  id: str | None = None, **show: Any) -> int | str | None:
        """Your answer: an option's index, or with no options the text you typed. None when
        there's no answer, and then the question is taken off the screen."""
        asked = next(Channels.ids)
        show = {k: v for k, v in show.items() if v is not None} | Popup.draw(id, Popup.POOL)

        try:
            options = None if options is None else paired(options)
            answer = await request("usr", {"id": asked, "context": context, "options": options, "show": show}, timeout)
        except asyncio.CancelledError:  # no longer asked: off the screen (and its sound stops)
            Popup.send({"type": "cancel", "id": asked})
            raise

        if answer is None:       await Channels.bus.publish("proki.ui", {"type": "cancel", "id": asked})
        if options is not None:  return picked(answer, options)
        return answer if isinstance(answer, str) and answer.strip() else None

    # --- telling -----------------------------------------------------------------------------

    @staticmethod
    def send(message: dict) -> None:
        """A one-way message. Sent on the engine's loop, in the order sent."""
        asyncio.get_running_loop().create_task(Channels.bus.publish("proki.ui", message))

    @staticmethod
    def poke(text: str, title: str | None = None, id: str | None = None) -> None:
        """A message to read: its `title`, and a picture and a sound drawn from the picks of `id`."""
        Popup.send({"type": "poke", "text": text, **({"title": title} if title else {}), **Popup.draw(id)})

    @staticmethod
    def draw(id: str | None, pool: str | None = None) -> dict[str, str]:
        """A picture and a sound, as their files, drawn from the picks of `id` and the keys of
        `pool`: {"media": ..., "sound": ...}, one with none left out."""
        library = Popup.library
        if library is None:  return {}

        keys  = [*(library.get_pool(pool) if pool else []), *(library.get_picks(id) if id else [])]
        drawn = {"media": library.draw(keys, "image"), "sound": library.draw(keys, "sound")}
        return {name: file for name, file in drawn.items() if file}

    @staticmethod
    def open(view: str) -> None:
        Popup.send({"type": "open", "view": view})


def paired(options: Options) -> list[list]:
    """Each option as [label, criteria] ("Start" becomes ["Start", None])."""
    return [list(o) if isinstance(o, tuple) else [o, None] for o in options]


def picked(answer: Any, options: list) -> int | None:
    """`answer` if it's the index of one of `options`, else None."""
    return answer if isinstance(answer, int) and not isinstance(answer, bool) and 0 <= answer < len(options) else None
