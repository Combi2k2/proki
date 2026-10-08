"""The grand gesture (the legacy grand gesture flow's) (core/grand.py): choose the one big thing and
the length, and afterwards note what got done."""

from __future__ import annotations

from datetime import datetime, timezone

from proki.core.ui import Ui
from proki.legacy.core.grand import GrandParams
from proki.legacy.core.store import Store
from proki.legacy.core.backlog import minutes_text
from proki.programs.base import Ritual, program


class Grand(Ritual):
    def __init__(self, store: Store, params: GrandParams = GrandParams()):
        super().__init__("grand")
        self.store = store
        self.params = params

    def start(self) -> None:
        task = program("plan").next_task(datetime.now(timezone.utc))[1]
        Ui.ask_text(
            "Grand gesture: a long stretch on one big thing, ideally somewhere unusual. What's the one thing?",
            self._what, placeholder="e.g. finish the PhD proposal draft", skip_label="Cancel",
            text=task.title if task else "")

    def _what(self, what: str | None) -> None:
        if what is None:
            return
        Ui.ask(f"How long for “{what}”? (Breaks are fine; wrap-up only at the end.)",
                       lambda a: program("session").start_grand(what, int(a)) if a != "cancel" else None,
                       [(label, str(hours)) for label, hours in self.params.lengths] + [("Cancel", "cancel")])

    def finished(self, what: str, deep_minutes: int) -> None:
        Ui.ask_text(
            f"Grand gesture done: {minutes_text(deep_minutes)} of deep work on “{what}”. What did you get done?",
            lambda text: self.store.add_note(f"Grand gesture, “{what}”: {text}", None, datetime.now(timezone.utc))
            if text else None,
            placeholder="what's finished, what's next", skip_label="Skip")


