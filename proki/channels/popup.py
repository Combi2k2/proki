"""The popup: everything proki says to you, through the UI (ui/main.js).

Asking, on the "usr" channel ("proki.ask.usr"): the question waits for your answer, and
the answer goes back to whoever asked. That one does what it means.

    await Popup.ask("Start?", ["Start", "Not now"])               1         the option's index
    await Popup.ask("Anything still open?", placeholder="...")    "milk"    the text you typed
                                                                  None      dismissed, or too late

    how it's shown (`show`):
        urgent=True          before the questions waiting their turn
        placeholder="..."    the empty text box's hint
        skip="That's all"    the button that answers nothing
        text="..."           what's typed already

Telling, one way ("proki.ui"): nothing comes back.

    Popup.poke("Back to work")      {"type": "poke", "text": ...}            a message to read
    Popup.poke("Away?", alarm=True) {"type": "poke", ..., "alarm": true}     ringing while it's shown
    Popup.open("task_form")         {"type": "open", "view": ...}            a view: task_form, task_board
    Popup.send({"type": ...})       any other:
                                    "status"   the tray's line, each cycle
                                    "quit"     the UI closes
                                    "cancel"   a question no longer asked (`ask` sends it)

The UI shows one question at a time: the others wait their turn, and one that's too late,
or no longer asked (whoever asked moved on), leaves the line ("cancel"). A poke's alarm
rings only while the poke is on the screen: closing it stops the alarm at once. Whether a question waits is the channel's (`queued("usr")`, base.py).
"""

from __future__ import annotations

import asyncio
from typing import Any

from proki.channels.base import (
    Channels,
    Options,
    paired,
    picked,
    request
)

class Popup:
    # --- asking ------------------------------------------------------------------------------

    @staticmethod
    async def ask(context: str, options: Options | None = None, timeout: float = 120, **show: Any) -> int | str | None:
        """Your answer: an option's index, or with no options the text you typed. None when
        there's no answer, and then the question is taken off the screen."""
        id = next(Channels.ids)
        
        try:
            options = None if options is None else paired(options)
            answer = await request("usr", {"id": id, "context": context, "options": options, "show": show}, timeout)
        except asyncio.CancelledError:  # no longer asked: off the screen (and its alarm stops)
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
    def poke(text: str, alarm: bool = False) -> None:
        Popup.send({"type": "poke", "text": text, **({"alarm": True} if alarm else {})})

    @staticmethod
    def open(view: str) -> None:
        Popup.send({"type": "open", "view": view})
