"""What proki's own primitives (this folder) share: `Labeled`, the window in focus as the
app labels it, through a function the app sets (the labels, jev, the user's answers:
more than a field of what was recorded)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.primitives.aw.base import focused
from proki.services import aw


class Labeled:
    """Mixin: `of(app, title)`, of the window in focus."""

    buckets = (aw.WINDOW,)

    def of(self, app: str, title: str) -> Any:
        raise NotImplementedError

    def read(self, rec: aw.Record | None, t: datetime) -> Any:
        e = focused(rec, t)
        return self.of(e.data.get("app", ""), e.data.get("title", "")) if e else None
