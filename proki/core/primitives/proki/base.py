"""What proki's own primitives (this folder) share: `Labeled`, a value about the window in
focus that comes from the app's labels, not from a field ActivityWatch recorded. The app
plugs in the function (it knows the labels, jev's guesses and your answers).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.primitives.aw.base import focused, tab_url
from proki.services import aw


class Labeled:
    """Mixin: the value `of(app, url)` gives for the window in focus. Unknown when no
    window is in focus."""

    buckets = (aw.WINDOW, aw.WEBTAB)

    def of(self, app: str, url: str | None) -> Any:
        """The value for a window, from its app and its tab's address (None: not a browser's)."""
        raise NotImplementedError

    def read(self, t: datetime) -> Any:
        e = focused(t)
        return self.of(e.data.get("app", ""), tab_url(t)) if e else None
