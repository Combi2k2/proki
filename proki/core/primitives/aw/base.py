"""What the ActivityWatch primitives (this folder) share:

    Recording         what ActivityWatch recorded, fetched once a run with the app's client
    focused(t)        the window watcher's event at time t: the app and window in focus
    Window            mixin: one field of that event (app, title)
    InputRate         mixin: input per minute over the cycle (keys, mouse_*)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from proki.core.primitives.base import Primitive
from proki.core.signals.stream import Stream
from proki.services import aw


class Recording:
    """What ActivityWatch recorded, for the primitives of this folder. The app gives the
    client (`Recording.client`, its one ActivityWatch client). Before each run's cycles,
    `fetch` gets what was recorded since the last run, and reads every bucket the
    primitives need right away, so a server that doesn't answer stops the run before any
    stream moves on. Without a client (tests), `rec` is used as it's given."""

    client: ClassVar[aw.ActivityWatchClient | None] = None
    rec: ClassVar[aw.Record | None] = None  # the run's recording

    @classmethod
    def fetch(cls, start: datetime, end: datetime) -> None:
        if cls.client is not None:
            cls.rec = aw.Record.fetch(start, end, cls.client, cls.rec)
        if cls.rec is None:
            return
        for bucket in sorted({b for s in Stream.registry.values() for b in getattr(s, "buckets", ())}):
            cls.rec[bucket]


Primitive.sources.append(Recording.fetch)


def focused(t: datetime) -> aw.Event | None:
    """The window watcher's event at `t`: the app and window in focus."""
    return None if Recording.rec is None else Recording.rec[aw.WINDOW].covering(t)


class Window:
    """Mixin: one field (`field`) of the window in focus, e.g. "app" or "title"."""

    buckets = (aw.WINDOW,)
    field: ClassVar[str]

    def read(self, t: datetime) -> Any:
        e = focused(t)
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

    def read(self, t: datetime) -> Any:
        rec = Recording.rec
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
