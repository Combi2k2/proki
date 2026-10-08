"""What programs written in code say to you: questions, and one-way messages to the UI.

A program asks through `Ui`, which asks in the background (`ask_later`, core/ask.py) and
calls back with the answer at the engine's next turn:

    Ui.ask("Start a session?", on_answer, [("Start session", "start"), ("Not now", "no")])
    Ui.ask_text("Anything still open?", on_text, placeholder="…", skip_label="That's all")
    Ui.busy()                                  # a question is waiting (or the app's own window is up)

`on_answer` gets the option's code. It isn't called without an answer. These questions
wait for you as long as it takes (a day at most).

One-way messages go to the UI on the bus ("proki.ui"):

    {"type": "poke", "text": "..."}                        a message, nothing to answer
    {"type": "alarm", "id": "session", "on": true}         an alarm rings until it's turned off
    {"type": "session", "minutes": 12, "extra": "5 min left"}   the running session (minutes: null, none)
    {"type": "hide"}                                       take the question on screen down, unanswered
    {"type": "cancel", "id": 3}                            question 3 is no longer asked (core/ask.py)
    {"type": "lock"}                                       lock the screen
    {"type": "open", "view": "task_form"}                  open a view: task_form, task_board
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from proki.core.ask import UI, Asking, ask_later, waiting
from proki.utils import fill

OK = [("Got it", "ok")]
DAY = 24 * 3600  # how long a program's question waits, in seconds


class Ui:
    elsewhere: ClassVar[Callable[[], bool]] = staticmethod(lambda: False)  # the app has a window up of its own

    @staticmethod
    def send(message: dict) -> None:
        """A one-way message to the UI."""
        Asking.bus.publish(UI, message)

    @staticmethod
    def ask(message: str, on_answer: Callable[[str], Any], options: list[tuple[str, str]] = OK,
            values: dict[str, Any] | None = None, alarm: str | None = None, urgent: bool = False) -> None:
        """`options`: (label, code). `values` fill `message`'s {name}s. `alarm`: ring alarm
        `alarm` while it's asked. `urgent`: shown at once, before the questions waiting their turn."""
        codes = [code for _, code in options]

        def answered(index: int | None) -> None:
            if alarm:
                Ui.alarm(alarm, False)
            if index is not None:
                on_answer(codes[index])

        if alarm:
            Ui.alarm(alarm, True)
        ask_later(answered, "usr", fill(message, values or {}), [label for label, _ in options], timeout=DAY,
                  show={"urgent": True} if urgent else {})

    @staticmethod
    def ask_text(message: str, on_text: Callable[[str | None], Any], placeholder: str = "",
                 skip_label: str = "Skip", text: str = "") -> None:
        """`on_text` gets the text, or None when skipped."""
        ask_later(on_text, "usr", message, None, timeout=DAY,
                  show={"placeholder": placeholder, "skip": skip_label, "text": text})

    @staticmethod
    def busy() -> bool:
        return waiting("usr") > 0 or Ui.elsewhere()

    @staticmethod
    def poke(text: str) -> None:
        Ui.send({"type": "poke", "text": text})

    @staticmethod
    def alarm(id: str, on: bool) -> None:
        Ui.send({"type": "alarm", "id": id, "on": on})

    @staticmethod
    def session(minutes: int | None, extra: str | None = None) -> None:
        Ui.send({"type": "session", "minutes": minutes, "extra": extra})

    @staticmethod
    def hide() -> None:
        Ui.send({"type": "hide"})

    @staticmethod
    def lock() -> None:
        Ui.send({"type": "lock"})

    @staticmethod
    def open(view: str) -> None:
        Ui.send({"type": "open", "view": view})


class Alarm:
    """One named alarm in the UI: start, stop, and whether it's ringing."""

    def __init__(self, id: str):
        self.id = id
        self.ringing = False

    def start(self) -> None:
        self.ringing = True
        Ui.alarm(self.id, True)

    def stop(self) -> None:
        if self.ringing:
            self.ringing = False
            Ui.alarm(self.id, False)
