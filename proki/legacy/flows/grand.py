"""The grand gesture in the running app (core/grand.py): choose the one big thing and
the length, and afterwards note what got done."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from proki.legacy.flows.base import Flow
from proki.legacy.core.backlog import Task, minutes_text
from proki.legacy.core.grand import GrandParams
from proki.legacy.core.store import Store
from proki.legacy.ui.popup import Popup


class GrandFlow(Flow):
    def __init__(self, store: Store, popup: Popup, start_grand: Callable[[str, int], None],
                 next_task: Callable[[], Task | None], params: GrandParams = GrandParams()):
        self.store = store
        self.popup = popup
        self.start_grand = start_grand  # (what, hours): starts the long session
        self.next_task = next_task
        self.params = params

    def start(self) -> None:
        task = self.next_task()
        self.popup.ask_text(
            "Grand gesture: a long stretch on one big thing, ideally somewhere unusual. What's the one thing?",
            self._what, placeholder="e.g. finish the PhD proposal draft", skip_label="Cancel",
            text=task.title if task else "")

    def _what(self, what: str | None) -> None:
        if what is None:
            return
        self.popup.ask(f"How long for “{what}”? (Breaks are fine; wrap-up only at the end.)",
                       lambda a: self.start_grand(what, int(a)) if a != "cancel" else None,
                       [(label, str(hours)) for label, hours in self.params.lengths] + [("Cancel", "cancel")])

    def finished(self, what: str, deep_minutes: int) -> None:
        self.popup.ask_text(
            f"Grand gesture done: {minutes_text(deep_minutes)} of deep work on “{what}”. What did you get done?",
            lambda text: self.store.add_note(f"Grand gesture, “{what}”: {text}", None, datetime.now(timezone.utc))
            if text else None,
            placeholder="what's finished, what's next", skip_label="Skip")

    name = "grand gesture"

