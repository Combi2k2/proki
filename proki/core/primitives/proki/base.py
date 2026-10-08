"""What proki's own primitives (this folder) share: `Labeled`, a value about the window in
focus that comes from the app's labels, not from a field ActivityWatch recorded. The app
plugs in the function (it knows the labels, jev's guesses and your answers).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.primitives.aw.base import focused
from proki.services import aw


class Labeled:
    """Mixin: the value `of(app, title)` gives for the window in focus. Unknown when no
    window is in focus."""

    buckets = (aw.WINDOW,)

    def of(self, app: str, title: str) -> Any:
        """The value for a window, from its app and title."""
        raise NotImplementedError

    def read(self, t: datetime) -> Any:
        e = focused(t)
        return self.of(e.data.get("app", ""), e.data.get("title", "")) if e else None
