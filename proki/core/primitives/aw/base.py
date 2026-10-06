"""What the ActivityWatch primitives (this folder) share:

    focused(rec, t)   the window watcher's event at time t: the app and window in focus
    Window            mixin: one field of that event (app, title)
    InputRate         mixin: input per minute over the cycle (keys, mouse_*)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from proki.core.signals.stream import Stream
from proki.services import aw


def focused(rec: aw.Record | None, t: datetime) -> aw.Event | None:
    """The window watcher's event at `t`: the app and window in focus."""
    return None if rec is None else rec[aw.WINDOW].covering(t)


class Window:
    """Mixin: one field (`field`) of the window in focus, e.g. "app" or "title"."""

    buckets = (aw.WINDOW,)
    field: ClassVar[str]

    def read(self, rec: aw.Record | None, t: datetime) -> Any:
        e = focused(rec, t)
        return e.data.get(self.field) if e else None


class InputRate:
    """Mixin: input per minute, over the last cycle (from t − cycle to t).

    Every input event overlapping the cycle counts, each weighted by how much of it falls
    inside the cycle. If none does (the newest may not be written yet), the event holding
    at t is used. Input holds a little while after its event (`aw.HOLD`). `count` says
    what to count in an event's data."""

    buckets = (aw.INPUT,)

    def count(self, data: dict) -> float:
        """How much input one event holds (presses, clicks, pixels, ...)."""
        raise NotImplementedError

    def read(self, rec: aw.Record | None, t: datetime) -> Any:
        if rec is None:
            return None
        a = t - Stream.cycle
        weighted = known = 0.0
        for e in rec[aw.INPUT].overlapping(a, t):
            length = (e.end - e.start).total_seconds()
            if length <= 0:
                continue
            inside = (min(e.end, t) - max(e.start, a)).total_seconds()
            weighted += self.count(e.data) / (length / 60) * inside  # its rate, for its time inside
            known += inside
        if known:
            return weighted / known
        e = rec[aw.INPUT].covering(t)
        if e is None or e.end <= e.start:
            return None
        return self.count(e.data) / ((e.end - e.start).total_seconds() / 60)
