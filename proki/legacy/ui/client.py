"""The legacy Qt app as the engine's UI, on the message bus: it answers your questions
("proki.ask.usr", core/ask.py) and shows the one-way messages ("proki.ui", core/ui.py),
until a UI process takes over. Questions show in the popup one at a time (an urgent one
first, the others wait their turn, also while a legacy window has the popup); alarms, the
session in the tray, locking the screen, the task windows.

The bus calls in from its own threads, so what comes is queued (`serve`) and put on screen
from Qt's thread (`pump`, a timer of the app's).
"""

from __future__ import annotations

import itertools
import queue
from collections import deque
from collections.abc import Callable

from proki.legacy.ui.popup import Popup
from proki.utils import fill


class PopupClient:
    def __init__(self, popup: Popup, alarm: Callable[[], object] = lambda: None,
                 set_session: Callable[[int | None, str | None], None] = lambda minutes, extra: None,
                 lock_screen: Callable[[], None] = lambda: None, views: dict[str, Callable[[], None]] | None = None):
        self.popup = popup
        self.make_alarm = alarm  # a new alarm player (ui.sound.Alarm), one per alarm id
        self.alarms: dict[str, object] = {}
        self.set_session = set_session  # the tray's session line
        self.lock_screen = lock_screen
        self.views = views or {}  # what "open" opens, by name
        self.waiting: deque[dict] = deque()
        self.showing: dict | None = None  # the engine's question on screen
        self.inbox: queue.Queue[tuple[dict, Callable[[dict], None] | None]] = queue.Queue()  # from the bus
        self.replies: dict = {}  # question id → (its reply, its options' labels or None for text)
        self.pokes = itertools.count(1)

    def serve(self, bus) -> None:
        """Answer "proki.ask.usr" and show "proki.ui" (both queued for `pump`)."""
        bus.subscribe("proki.ask.usr", lambda request, reply: self.inbox.put((request, reply)), workers=4)
        bus.subscribe("proki.ui", lambda message, reply: self.inbox.put((message, None)))

    def pump(self) -> None:
        """What came over the bus, onto the screen (Qt's thread)."""
        while True:
            try:
                data, reply = self.inbox.get_nowait()
            except queue.Empty:
                return
            if reply is None:  # a one-way message
                if data.get("type") == "poke":
                    self.send({"type": "ask", "id": f"poke{next(self.pokes)}", "text": data.get("text", ""), "options": []})
                else:
                    self.send(data)
                continue
            options = data.get("options")
            labels = None if options is None else [label for label, _ in options]
            self.replies[data["id"]] = (reply, labels)
            show = data.get("show") or {}
            message = {"type": "ask" if labels is not None else "ask_text", "id": data["id"], "text": data["context"],
                       "options": labels or [], "urgent": bool(show.get("urgent")),
                       "placeholder": show.get("placeholder", ""), "skip": show.get("skip", "Skip"),
                       "default": show.get("text", "")}
            self.send(message)
        self.show_next()

    def reply(self, message: dict) -> None:
        """Your answer to a question (`_answer`), back over the bus: the option's index, or the text."""
        entry = self.replies.pop(message["id"], None)
        if entry is None:
            return  # a poke, or a question taken back
        respond, labels = entry
        option = message.get("option")
        if labels is None:
            respond({"answer": option if isinstance(option, str) else None})
        else:
            respond({"answer": labels.index(option) if option in labels else None})

    def send(self, message: dict) -> None:
        """A message from the engine."""
        kind = message.get("type")
        if kind in ("ask", "ask_text"):
            if message.get("urgent"):
                if self.showing is not None and self.popup.isVisible():
                    self.waiting.appendleft(self.showing)  # back in line, shown again after this one
                self._show(message)
            else:
                self.waiting.append(message)
                self.show_next()
        elif kind == "alarm":
            player = self.alarms.get(message["id"])
            if player is None:
                player = self.alarms[message["id"]] = self.make_alarm()
            if player is not None:
                player.start() if message["on"] else player.stop()
        elif kind == "session":
            self.set_session(message.get("minutes"), message.get("extra"))
        elif kind == "hide":
            if self.showing is not None and self.popup.isVisible():
                self.popup.hide()
                self._answer(self.showing, None)
        elif kind == "cancel":
            self.replies.pop(message["id"], None)
            self.waiting = deque(m for m in self.waiting if m["id"] != message["id"])
            if self.showing is not None and self.showing["id"] == message["id"]:
                self.showing = None
                self.popup.hide()
        elif kind == "lock":
            self.lock_screen()
        elif kind == "open" and message.get("view") in self.views:
            self.views[message["view"]]()

    def show_next(self) -> None:
        """The next question, if the popup is free (called again every tick)."""
        if self.waiting and not self.popup.isVisible():
            self._show(self.waiting.popleft())

    def _show(self, message: dict) -> None:
        self.showing = message
        text = fill(message["text"], message.get("values", {}))
        if message["type"] == "ask_text":
            self.popup.ask_text(text, lambda typed: self._answer(message, typed), placeholder=message.get("placeholder", ""),
                                skip_label=message.get("skip", "Skip"), text=message.get("default", ""))
        else:
            options = [(option, option) for option in message["options"]] or [("OK", "")]  # a notice
            self.popup.ask(text, lambda option: self._answer(message, option or None), options)

    def _answer(self, message: dict, option: str | None) -> None:
        if self.showing is message:
            self.showing = None
        self.reply({"type": "answer", "id": message["id"], "option": option})
